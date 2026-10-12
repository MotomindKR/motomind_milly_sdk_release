"""DXL teaching device -> isolated Milly RViz model; no robot driver."""
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, RegisterEventHandler
from launch.conditions import IfCondition
from launch.event_handlers import OnShutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from milly_sdk_ros.rviz_config import make_rviz_config, style_robot_description
from milly_sdk_ros.teaching_preview import PREFIX


def setup(context):
    namespace = "milly/teaching_preview"
    share = Path(get_package_share_directory("milly_sdk_description"))
    description = share / "milly_description"
    robot = (description / "urdf/MILLY.urdf").read_text().replace(
        "package://milly_description/", description.as_uri() + "/")
    directory, rviz_path = make_rviz_config(share / "rviz/milly.rviz", PREFIX)
    config = yaml.safe_load(Path(rviz_path).read_text())
    config["Visualization Manager"]["Displays"].append({
        "Class": "rviz_default_plugins/Marker", "Name": "Teaching input status", "Enabled": True,
        "Marker Topic": {"Value": "status_marker", "Depth": 1, "History Policy": "Keep Last",
                         "Reliability Policy": "Reliable", "Durability Policy": "Transient Local"}})
    Path(rviz_path).write_text(yaml.safe_dump(config, sort_keys=False))

    def cleanup(context):
        directory.cleanup()
        return []

    return [
        RegisterEventHandler(OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup)])),
        Node(package="milly_sdk_ros", executable="teaching_preview", namespace=namespace,
             output="screen", parameters=[{
                 name: ParameterValue(LaunchConfiguration(name), value_type=kind)
                 for name, kind in (("profile", str), ("port", str), ("fake", bool),
                                    ("rate_hz", float), ("read_timeout_s", float))}]),
        Node(package="robot_state_publisher", executable="robot_state_publisher", namespace=namespace,
             parameters=[{"robot_description": style_robot_description(robot), "frame_prefix": PREFIX + "/"}],
             remappings=[("/tf", "tf"), ("/tf_static", "tf_static")]),
        Node(package="rviz2", executable="rviz2", namespace=namespace,
             arguments=["-d", rviz_path], condition=IfCondition(LaunchConfiguration("gui")),
             remappings=[("/tf", "tf"), ("/tf_static", "tf_static")]),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("profile", description="Absolute path to mapped teaching JSON"),
        DeclareLaunchArgument("port", default_value="", description="DXL serial port; real default /dev/ttyUSB0; omit in fake mode"),
        DeclareLaunchArgument("fake", default_value="false", choices=["true", "false"]),
        DeclareLaunchArgument("gui", default_value="true", choices=["true", "false"]),
        DeclareLaunchArgument("rate_hz", default_value="30.0"),
        DeclareLaunchArgument("read_timeout_s", default_value="0.25"),
        OpaqueFunction(function=setup),
    ])
