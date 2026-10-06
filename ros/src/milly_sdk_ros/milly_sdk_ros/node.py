"""Humble service/topic facade. No automatic enable, reconnect, or command replay."""
import math
import signal
import threading
import time

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from rcl_interfaces.msg import ParameterDescriptor
from std_srvs.srv import Trigger
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseStamped
from milly_sdk_interfaces.msg import MitCommand, MotorState, MotorStates, DriverStatus
from milly_sdk_interfaces.srv import (
    MoveJ, MoveP, Gripper, FloatMode, SetMaxVel, SetGains, GetRobotInfo, Fk,
)
from .backend import Backend, optional
from .telemetry import joint_values, quaternion
from .position_monitor import GripperDisplayMap


class Driver(Node):
    def __init__(self, backend_factory=Backend.connect, **node_kwargs):
        super().__init__("milly_driver", **node_kwargs)
        def parameter(name, default):
            return self.declare_parameter(
                name, default, ParameterDescriptor(read_only=True)).value
        product_id = parameter("product_id", "")
        urdf = parameter("urdf_path", "")
        motor_gui = parameter("motor_gui", False)
        rate = float(parameter("supervisor_rate_hz", 100.0))
        publish_rate = float(parameter("publish_rate_hz", 30.0))
        stale = float(parameter("feedback_stale_s", 0.5))
        self.frame_prefix = parameter("frame_prefix", product_id + "/")
        if not product_id or not urdf:
            raise ValueError("product_id and urdf_path are required; use bringup.launch.py")
        if not math.isfinite(publish_rate) or not 1 <= publish_rate <= 100:
            raise ValueError("publish_rate_hz must be within [1, 100]")
        if not math.isfinite(stale) or stale <= 0:
            raise ValueError("feedback_stale_s must be finite and positive")
        self.backend = backend_factory(product_id, urdf, supervisor_rate_hz=rate,
                                       stale_after_s=stale)
        self.motor_window = None
        if motor_gui:
            try:
                from motomind_milly._position_gui_process import PositionProcessMonitor, motor_feedback_snapshot
                self.motor_window = PositionProcessMonitor(
                    self.backend.arm.manager, self.backend.config,
                    feedback_snapshot=lambda: motor_feedback_snapshot(self.backend.arm.manager, stale),
                    title=f"{product_id} — motor feedback", poll_ms=100)
                self.motor_window.start(wait=True)
            except BaseException:
                if self.motor_window is not None:
                    self.motor_window.close(wait=True)
                # GUI opens before services/enable: close the unused connection.
                self.backend.arm.disconnect()
                super().destroy_node()
                raise
        self._warning_at = 0.0
        commands = ReentrantCallbackGroup()
        stops = ReentrantCallbackGroup()
        telemetry = MutuallyExclusiveCallbackGroup()
        self._joint_pub = self.create_publisher(JointState, "joint_states", qos_profile_sensor_data)
        # RViz-only positions include an estimated finger opening. Keep the
        # measured joint_states API free of synthetic finger displacement.
        self._display_pub = self.create_publisher(JointState, "display_joint_states", qos_profile_sensor_data)
        self._gripper_display = GripperDisplayMap()
        self._motor_pub = self.create_publisher(MotorStates, "motor_states", qos_profile_sensor_data)
        self._pose_pub = self.create_publisher(PoseStamped, "flange_pose", qos_profile_sensor_data)
        self._status_pub = self.create_publisher(DriverStatus, "status", 1)
        self._mit_sub = self.create_subscription(
            MitCommand, "move_mit", self._mit, 1, callback_group=commands)
        for name in ("enable", "recover", "hold_mode"):
            self._service(Trigger, name,
                          lambda req, resp, op=name: self._execute(resp, op), commands)
        for name in ("disable", "shutdown", "emergency_stop"):
            operation = "electronic_emergency_stop" if name == "emergency_stop" else name
            self._service(Trigger, name,
                          lambda req, resp, op=operation: self._respond(
                              resp, self.backend.stop(op)), stops)
        self._service(MoveJ, "move_j",
                      lambda req, resp: self._motion(req, resp, "move_j", "positions"), commands)
        self._service(MoveP, "move_p",
                      lambda req, resp: self._motion(req, resp, "move_p", "pose"), commands)
        self._service(Gripper, "gripper", self._gripper, commands)
        self._service(FloatMode, "float_mode", self._float, commands)
        self._service(SetMaxVel, "set_max_vel",
                      lambda req, resp: self._execute(resp, "set_max_vel", max_vel=req.max_vel), commands)
        self._service(SetGains, "set_gains",
                      lambda req, resp: self._execute(
                          resp, "set_gains", group=req.group, kp=req.kp, kd=req.kd), commands)
        self._service(GetRobotInfo, "get_robot_info", self._info, commands)
        self._service(Fk, "fk", self._fk, commands)
        self._timer = self.create_timer(1.0 / publish_rate, self._publish, callback_group=telemetry)
        self.get_logger().warning(
            "Connected WITHOUT enable. Do not run another controller for this robot. "
            "shutdown/disable/emergency_stop affect motors, not just this ROS connection.")

    def destroy_node(self):
        if self.motor_window is not None:
            self.motor_window.close(wait=True)
        return super().destroy_node()

    def _service(self, kind, name, callback, group):
        # Node owns the service registry, including its built-in parameter services.
        self.create_service(kind, name, callback, callback_group=group)

    def _respond(self, response, result):
        response.success, response.message = result.success, result.message
        for name in ("duration_s", "target"):
            if hasattr(response, name):
                setattr(response, name, getattr(result, name))
        if not result.success:
            self._warn(result.message)
        return response

    def _execute(self, response, operation, **kwargs):
        return self._respond(response, self.backend.execute(operation, **kwargs))

    def _warn(self, message):
        # Continuous bad MIT publishers must not flood logs.
        now = time.monotonic()
        if now - self._warning_at >= 1.0:
            self.get_logger().warning(message)
            self._warning_at = now

    def _motion(self, req, resp, operation, vector):
        try:
            kwargs = {vector: list(getattr(req, vector))}
            kwargs.update({name: optional(getattr(req, name)) for name in ("max_vel", "kp", "kd")})
            if kwargs["max_vel"] is not None and not 0 < kwargs["max_vel"] <= 2.0:
                raise ValueError("max_vel must be within (0, 2.0] rad/s")
            return self._execute(resp, operation, **kwargs)
        except Exception as exc:
            return self._respond(resp, self.backend.fail(exc))

    def _mit(self, msg):
        try:
            result = self.backend.execute(
                "move_mit", motor_id=msg.motor_id, position=msg.position,
                velocity=msg.velocity, torque_feedforward=msg.torque_feedforward,
                kp=optional(msg.kp), kd=optional(msg.kd))
            if not result.success:
                self._warn(result.message)
        except Exception as exc:
            self.backend.fail(exc)
            self._warn(str(exc))

    def _gripper(self, req, resp):
        try:
            return self._execute(resp, "gripper", action=req.operation, position=req.position,
                                 kp=optional(req.kp), kd=optional(req.kd))
        except Exception as exc:
            return self._respond(resp, self.backend.fail(exc))

    def _float(self, req, resp):
        try:
            return self._execute(resp, "float_mode")
        except Exception as exc:
            return self._respond(resp, self.backend.fail(exc))

    def _info(self, req, resp):
        try:
            for key, value in self.backend.info().items():
                setattr(resp, key, value)
            resp.success = True
        except Exception as exc:
            self._respond(resp, self.backend.fail(exc))
        return resp

    def _fk(self, req, resp):
        result = self.backend.fk(req.joints)
        if result.success:
            resp.pose = result.values
        return self._respond(resp, result)

    def _publish(self):
        try:
            rows = self.backend.snapshots()
            status = self.backend.status()
            now = self.get_clock().now().to_msg()
            motors = MotorStates()
            motors.header.stamp = now
            motors.header.frame_id = self.frame_prefix + "base_link"
            motors.motors = [MotorState(**r) for r in rows]
            self._motor_pub.publish(motors)
            state = DriverStatus(**status)
            state.header = motors.header
            self._status_pub.publish(state)
            names, positions, velocities = joint_values(rows, self.backend.gripper.range)
            if names and status["connected"]:
                msg = JointState()
                msg.header = motors.header
                msg.name, msg.position, msg.velocity = names, positions, velocities
                # No invented effort for the finger linkage.
                self._joint_pub.publish(msg)
            if status["connected"]:
                display = JointState()
                display.header = motors.header
                display.name, display.position = list(names), list(positions)
                gripper = next((row for row in rows if row["joint_name"] == "gripper"), None)
                if gripper is not None and gripper["fresh"]:
                    finger = self._gripper_display.position(gripper["position"])
                    display.name.extend(["finger_1_joint", "finger_2_joint"])
                    display.position.extend([finger, finger])
                # No inferred finger velocity/effort. Missing/stale feedback
                # must not create a zero-valued finger transform.
                if display.name:
                    self._display_pub.publish(display)
            if status["connected"] and all(f"joint_{i}" in names for i in range(1, 7)):
                result = self.backend.fk([])
                if result.success:
                    pose = PoseStamped()
                    pose.header = motors.header
                    x, y, z, roll, pitch, yaw = result.values
                    pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = x, y, z
                    q = quaternion(roll, pitch, yaw)
                    pose.pose.orientation.x, pose.pose.orientation.y = q[0], q[1]
                    pose.pose.orientation.z, pose.pose.orientation.w = q[2], q[3]
                    self._pose_pub.publish(pose)
        except Exception as exc:
            self.backend.fail(exc)
            self._warn(f"telemetry failed: {exc}")


def main(args=None):
    # Keep ROS alive until damping completes; default rclpy signal handlers
    # otherwise invalidate the context before the graceful cleanup finishes.
    stop = threading.Event()
    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, lambda *_: stop.set())
    node = None
    executor = None
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    try:
        node = Driver()
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(node)
        while rclpy.ok() and not stop.is_set():
            executor.spin_once(timeout_sec=0.1)
    finally:
        if node is not None:
            result = node.backend.stop("shutdown")
            if not result.success:
                node.get_logger().error(f"shutdown failed: {result.message}")
        if executor is not None:
            executor.shutdown()
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
