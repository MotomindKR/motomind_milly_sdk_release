"""Single SDK control owner; display can be launched separately without CAN."""
from pathlib import Path
import re

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def setup(context):
    product = LaunchConfiguration("product_id").perform(context)
    if not re.fullmatch(r"MILLY_[A-Za-z0-9]{1,10}", product):
        raise ValueError("product_id must be the engraved MILLY_<code>")
    share = Path(get_package_share_directory("milly_sdk_description"))
    description = share / "milly_description"
    return [
        SetEnvironmentVariable("MOTOMIND_MILLY_DESCRIPTION_DIR", str(description)),
        Node(package="milly_sdk_ros", executable="driver", namespace="milly/" + product,
             output="screen", parameters=[{
                 "product_id": product,
                 "motor_gui": ParameterValue(LaunchConfiguration("motor_gui"), value_type=bool),
                 "urdf_path": str(description / "urdf/MILLY.urdf"),
                 "frame_prefix": product + "/",
                 "supervisor_rate_hz": ParameterValue(LaunchConfiguration("supervisor_rate_hz"), value_type=float),
                 "publish_rate_hz": ParameterValue(LaunchConfiguration("publish_rate_hz"), value_type=float),
                 "feedback_stale_s": ParameterValue(LaunchConfiguration("feedback_stale_s"), value_type=float),
             }]),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(share / "launch/display.launch.py")),
            launch_arguments={"product_id": product, "gui": "true"}.items(),
            condition=IfCondition(LaunchConfiguration("gui"))),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("product_id", description="Required engraved MILLY ID"),
        DeclareLaunchArgument("motor_gui", default_value="true", choices=["true", "false"]),
        DeclareLaunchArgument("gui", default_value="false", choices=["true", "false"],
                              description="Also launch feedback display/RViz"),
        DeclareLaunchArgument("supervisor_rate_hz", default_value="100.0"),
        DeclareLaunchArgument("publish_rate_hz", default_value="30.0"),
        DeclareLaunchArgument("feedback_stale_s", default_value="0.5"),
        OpaqueFunction(function=setup),
    ])
