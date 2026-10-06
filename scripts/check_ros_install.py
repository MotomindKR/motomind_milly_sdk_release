"""Check a Humble installation. No CAN connection or Arm creation."""
from pathlib import Path
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
from milly_sdk_interfaces.srv import MoveJ, MoveP, Gripper, Fk, FloatMode
from milly_sdk_interfaces.msg import MitCommand
from milly_sdk_ros.node import Driver
import motomind_milly as mm
from motomind_robot_model import RobotModel

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
print("Installed interfaces, model, factory calibration and collision meshes: OK (no hardware)")
