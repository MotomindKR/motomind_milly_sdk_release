"""Passive RAW-joint display; intentionally exposes NO control services/topics."""
import json
import signal
import threading
from dataclasses import asdict

import rclpy
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import JointState
from std_msgs.msg import String

from .position_monitor import GripperDisplayMap, PositionMonitor


class DescriptionMonitor(Node):
    def __init__(self, **node_kwargs):
        super().__init__("description_monitor", **node_kwargs)
        product = self.declare_parameter("product_id", "").value
        motor_gui = self.declare_parameter("motor_gui", False).value
        self.gripper_display = GripperDisplayMap(**{
            name: self.declare_parameter(
                "gripper_" + name, default,
                ParameterDescriptor(read_only=True)).value
            for name, default in asdict(GripperDisplayMap()).items()})
        self.motor_window = None
        import motomind_milly as mm
        from motomind_milly import profile
        config, _ = profile.load_robot_profile(product)
        if any(m.direction != 1 for m in config.motors):
            raise RuntimeError("Install the RAW-coordinate SDK wheel: all directions must be +1")
        self.joints = self.create_publisher(JointState, "joint_states", 10)
        self.status = self.create_publisher(String, "description_status", 10)
        self.timer = self.create_timer(1 / 30, self.publish_positions)
        # create_arm opens the socket; it does not enable or start supervisor.
        arm = mm.create_arm(product, supervisor_rate_hz=100)
        self.monitor = PositionMonitor(arm)
        try:
            self.monitor.start()
            if motor_gui:
                from motomind_milly.monitor import MotorMonitor
                self.motor_window = MotorMonitor(
                    arm.manager, config, owns_arm=False,
                    title=f"{product} — RAW motor positions (no control)",
                    position_snapshot=self.monitor.snapshot)
                self.motor_window.start(wait=True)
        except BaseException:
            if self.motor_window is not None:
                self.motor_window.close(wait=True)
            self.monitor.close()
            raise
        self.get_logger().warning(
            "POSITION QUERIES ONLY: no enable/disable/damping. Ensure torque is already OFF, "
            "stop other controllers and support the arm. Fingers use an uncalibrated linear "
            "display estimate from motor 7, not measured finger displacement.")

    def destroy_node(self):
        if self.motor_window is not None:
            self.motor_window.close(wait=True)
        if hasattr(self, "monitor"):
            self.monitor.close()
        return super().destroy_node()

    def publish_positions(self):
        rows = self.monitor.snapshot()
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        for mid in range(1, 7):
            row = rows.get(mid)
            if row and row["fresh"]:
                message.name.append(f"joint_{mid}")
                message.position.append(row["position"])
        gripper = rows.get(7)
        finger_position = None
        if gripper and gripper["fresh"]:
            finger_position = self.gripper_display.position(gripper["position"])
            message.name.extend(["finger_1_joint", "finger_2_joint"])
            message.position.extend([finger_position, finger_position])
        # Only position was queried: do not falsely publish fresh velocity/effort.
        if message.name:
            self.joints.publish(message)
        missing = [mid for mid in range(1, 8) if mid not in rows]
        stale = [mid for mid, row in rows.items() if not row["fresh"]]
        self.status.publish(String(data=json.dumps({
            "coordinates": "motor_raw", "control_enabled_by_this_node": False,
            "feedback_valid": not missing and not stale, "missing_motor_ids": missing,
            "stale_motor_ids": stale, "motors": rows,
            "finger_display": "linear_estimate_from_motor_7",
            "finger_position_m": finger_position,
            "finger_feedback_valid": finger_position is not None,
            "finger_mapping": asdict(self.gripper_display),
            "error": self.monitor.last_error})))


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    stop = threading.Event()
    previous = {s: signal.signal(s, lambda *_: stop.set()) for s in (signal.SIGINT, signal.SIGTERM)}
    node = None
    try:
        node = DescriptionMonitor()
        while rclpy.ok() and not stop.is_set():
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        for s, handler in previous.items():
            signal.signal(s, handler)
