"""Read-only teaching input -> RViz. No Milly connection or DXL control writes."""
import math

import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.qos import QoSProfile, DurabilityPolicy
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from visualization_msgs.msg import Marker

from .position_monitor import GripperDisplayMap

JOINTS = tuple(f"joint_{i}" for i in range(1, 7)) + ("gripper",)
PREFIX = "MILLY_PREVIEW"


def make_device(port, profile, *, fake, read_timeout_s):
    # Optional dependency: regular Milly ROS nodes do not need the teaching SDK.
    from motomind_teaching import TeachingDevice
    from motomind_teaching._profiles import load_profile
    transport = None
    if fake:
        from motomind_teaching.device import MODELS
        from motomind_teaching.testing import FakeTransport
        data = load_profile(profile)
        model_ids = {name: number for number, name in MODELS.items()}
        transport = FakeTransport(data["ids"], model={
            mid: model_ids[model] for mid, model in zip(data["ids"], data["models"])})
    return TeachingDevice.from_profile(port, profile, transport=transport,
                                       read_timeout_s=read_timeout_s)


class TeachingPreview(Node):
    def __init__(self, *, device_factory=make_device, **kwargs):
        kwargs.setdefault("namespace", "/milly/teaching_preview")
        super().__init__("teaching_preview", **kwargs)
        self.device = None
        self.fault = ""
        try:
            def param(name, default):
                return self.declare_parameter(
                    name, default, ParameterDescriptor(read_only=True)).value
            profile = param("profile", "")
            port = param("port", "")
            fake = param("fake", False)
            rate = param("rate_hz", 30.0)
            timeout = param("read_timeout_s", 0.25)
            if not math.isfinite(rate) or not 1 <= rate <= 100:
                raise ValueError("rate_hz must be in 1..100")
            if not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("read_timeout_s must be finite and positive")
            if not profile:
                raise ValueError("profile is required (mapped teaching JSON)")
            from motomind_teaching._profiles import load_profile
            data = load_profile(profile)
            if tuple(data.get("joint_names", [])) != JOINTS:
                raise ValueError("profile joint_names must be joint_1..joint_6, gripper in that order")
            if fake and port:
                raise ValueError("fake:=true cannot be combined with a real port")
            port = port or ("" if fake else "/dev/ttyUSB0")
            self._factory = lambda: device_factory(port, profile, fake=fake, read_timeout_s=timeout)
            self._source = "FAKE" if fake else "DXL READ ONLY"
            self._gripper = GripperDisplayMap()
            self.joints = self.create_publisher(JointState, "joint_states", 1)
            self.mapped = self.create_publisher(JointState, "mapped_positions", 1)
            retained = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
            self.status = self.create_publisher(String, "status", retained)
            self.marker = self.create_publisher(Marker, "status_marker", retained)
            self._status("WAITING FOR INPUT", error=False)
            self.timer = self.create_timer(1.0 / rate, self.poll)
        except BaseException:
            super().destroy_node()
            raise

    def _status(self, text, *, error):
        text = f"{self._source}: {text}"
        self.status.publish(String(data=text))
        marker = Marker()
        marker.header.frame_id = PREFIX + "/base_link"
        # A zero stamp makes this text visible even after dynamic TF stops.
        marker.ns = "teaching_preview_status"
        marker.id = 0
        marker.type = Marker.TEXT_VIEW_FACING
        marker.action = Marker.ADD
        marker.pose.position.z = 0.8
        marker.pose.orientation.w = 1.0
        marker.scale.z = 0.035
        marker.color.a = 1.0
        marker.color.r = 1.0 if error else 0.1
        marker.color.g = 0.1 if error else 1.0
        marker.text = text
        self.marker.publish(marker)

    def poll(self):
        if self.fault:
            return  # Explicit restart required; never replay cached input.
        try:
            if self.device is None:
                self.device = self._factory()
                self.device.open()
            positions = tuple(self.device.read_positions())
            if len(positions) != 7 or not all(math.isfinite(x) for x in positions):
                raise ValueError("expected seven finite mapped positions")
            fingers = self._gripper.position(positions[6])
            stamp = self.get_clock().now().to_msg()
            output = JointState()
            output.header.stamp = stamp
            output.name = list(JOINTS)
            output.position = list(positions)
            display = JointState()
            display.header.stamp = stamp
            display.name = list(JOINTS[:6]) + ["finger_1_joint", "finger_2_joint"]
            display.position = list(positions[:6]) + [fingers, fingers]
            self.mapped.publish(output)
            self.joints.publish(display)
            self._status("LIVE / gripper estimated", error=False)
        except Exception as exc:
            self.fault = str(exc) or type(exc).__name__
            self.timer.cancel()
            if self.device is not None:
                try:
                    self.device.close()
                except Exception as close_error:
                    self.fault += f"; close failed: {close_error}"
                self.device = None
            self.get_logger().error("Preview stopped: " + self.fault)
            self._status("FAULT - LAST POSE IS STALE / restart required", error=True)

    def destroy_node(self):
        try:
            if self.device is not None:
                self.device.close()
                self.device = None
        finally:
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = TeachingPreview()
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
