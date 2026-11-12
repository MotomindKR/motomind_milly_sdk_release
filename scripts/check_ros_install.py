"""Check a Humble installation. No CAN connection or Arm creation."""
from pathlib import Path
from importlib.metadata import distribution
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
expected = ET.parse(root/'ros/src/milly_sdk_ros/package.xml').findtext('version')
installed = distribution('milly-sdk-ros')
entries = {entry.name: entry for entry in installed.entry_points if entry.group == 'console_scripts'}
required = {'driver', 'discover', 'description_monitor', 'teaching_preview'}
assert installed.version == expected and required <= entries.keys(), (
    'ROS executable metadata is stale or incomplete. Run bash scripts/setup_ros_humble.sh, '
    'then source scripts/ros_env.sh in a fresh terminal.')
for name in required:
    assert callable(entries[name].load()), f'ROS executable cannot be loaded: {name}'

from ament_index_python.packages import get_package_share_directory
from rclpy.type_support import check_for_type_support
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger
from visualization_msgs.msg import Marker
from milly_sdk_interfaces.srv import (MoveJ, MoveP, Gripper, Fk, FloatMode,
                                      SetMaxVel, SetGains, GetRobotInfo)
from milly_sdk_interfaces.msg import MitCommand, MotorState, MotorStates, DriverStatus
from milly_sdk_ros.node import Driver
import motomind_milly as mm
from motomind_robot_model import RobotModel

# Importing a generated Python class alone does not load its native ROS type
# support. Check that too, before a user's first publisher/service is created.
for interface in (JointState, Marker, Trigger, MoveJ, MoveP, Gripper, Fk,
                  FloatMode, SetMaxVel, SetGains, GetRobotInfo, MitCommand,
                  MotorState, MotorStates, DriverStatus):
    check_for_type_support(interface)

assert FloatMode.Request.get_fields_and_field_types() == {}
assert MoveJ.Request().max_vel.tolist() == []
assert len(MoveP.Request().pose) == 6
assert Gripper.Request().operation == ""
assert Fk.Request().joints.tolist() == []
assert MitCommand().motor_id == 0
assert callable(Driver)
assert mm.MotorState().feedback_age_s == -1.0
bringup = Path(get_package_share_directory("milly_sdk_bringup"))
assert (bringup / "launch/bringup.launch.py").is_file()
description = Path(get_package_share_directory("milly_sdk_description"))
assert (description / "launch/display.launch.py").is_file()
assert not (description / "launch/bringup.launch.py").exists()
share = Path(get_package_share_directory("milly_sdk_description")) / "milly_description"
urdf = share / "urdf" / "MILLY.urdf"
for mesh in ET.parse(urdf).iter("mesh"):
    uri = mesh.get("filename")
    assert uri.startswith("package://milly_description/")
    path = share / uri.removeprefix("package://milly_description/")
    assert path.is_file(), path
model = RobotModel(str(urdf))
mm.profile.load_factory_gravity_calibration(model)
model.frame_id("link_6")
model.enable_self_collision([str(share.parent)])
print("Installed ROS executables, interface type support, model, factory calibration and collision meshes: OK (no hardware)")
