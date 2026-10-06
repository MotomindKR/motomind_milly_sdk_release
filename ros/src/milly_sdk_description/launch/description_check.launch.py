"""First hardware check: position queries + RViz, without any motor control."""
from pathlib import Path
import re

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnShutdown
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from milly_sdk_ros.rviz_config import make_rviz_config, style_robot_description
from milly_sdk_ros.position_monitor import GripperDisplayMap
from dataclasses import asdict


def setup(context):
    product = LaunchConfiguration("product_id").perform(context)
    if not re.fullmatch(r"MILLY_[A-Za-z0-9]{1,10}", product):
        raise ValueError("product_id must be the engraved MILLY_<code>")
    namespace = "milly/" + product + "/description_check"
    prefix = product + "/"
    share = Path(get_package_share_directory("milly_sdk_description"))
    description = share / "milly_description"
    robot = (description / "urdf/MILLY.urdf").read_text().replace(
        "package://milly_description/", description.as_uri() + "/")
    robot = style_robot_description(robot)
    rviz_dir, rviz_path = make_rviz_config(share / "rviz/milly.rviz", product)
    def cleanup_rviz(context):
        rviz_dir.cleanup()
        return []
    return [
        RegisterEventHandler(OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup_rviz)])),
        Node(package="milly_sdk_ros", executable="description_monitor", namespace=namespace,
             output="screen", parameters=[{"product_id": product,
                 "motor_gui": ParameterValue(LaunchConfiguration("motor_gui"), value_type=bool),
                 **{"gripper_" + name: ParameterValue(
                     LaunchConfiguration("gripper_" + name), value_type=float)
                    for name in asdict(GripperDisplayMap())}}]),
        Node(package="robot_state_publisher", executable="robot_state_publisher",
             namespace=namespace, parameters=[{"robot_description": robot, "frame_prefix": prefix}],
             remappings=[("/tf", "tf"), ("/tf_static", "tf_static")]),
        Node(package="rviz2", executable="rviz2", namespace=namespace,
             arguments=["-d", rviz_path],
             remappings=[("/tf", "tf"), ("/tf_static", "tf_static")],
             condition=IfCondition(LaunchConfiguration("rviz_gui"))),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("product_id", description="Required engraved MILLY ID"),
        DeclareLaunchArgument("gui", default_value="true", choices=["true", "false"],
                              description="Legacy fallback for both GUI flags; prefer rviz_gui/motor_gui"),
        DeclareLaunchArgument("rviz_gui", default_value=LaunchConfiguration("gui"), choices=["true", "false"]),
        DeclareLaunchArgument("motor_gui", default_value=LaunchConfiguration("gui"), choices=["true", "false"]),
        *[DeclareLaunchArgument("gripper_" + name, default_value=str(value),
                                description="RViz estimate endpoint (motor: rad, finger: m); no control")
          for name, value in asdict(GripperDisplayMap()).items()],
        OpaqueFunction(function=setup),
    ])
