"""Display an existing driver feedback stream; never opens CAN or enables motors."""
from pathlib import Path
import re

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnShutdown
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from milly_sdk_ros.rviz_config import make_rviz_config, style_robot_description


def setup(context):
    product = LaunchConfiguration("product_id").perform(context)
    if not re.fullmatch(r"MILLY_[A-Za-z0-9]{1,10}", product):
        raise ValueError("product_id must be the engraved MILLY_<code>")
    namespace = "milly/" + product
    prefix = product + "/"
    share = Path(get_package_share_directory("milly_sdk_description"))
    description = share / "milly_description"
    urdf = description / "urdf" / "MILLY.urdf"
    robot = urdf.read_text().replace("package://milly_description/", description.as_uri() + "/")
    robot = style_robot_description(robot)
    rviz_dir, rviz_path = make_rviz_config(share / "rviz/milly.rviz", product)
    def cleanup_rviz(context):
        rviz_dir.cleanup()
        return []
    return [
        RegisterEventHandler(OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup_rviz)])),
        Node(package="robot_state_publisher", executable="robot_state_publisher",
             namespace=namespace, parameters=[{"robot_description": robot, "frame_prefix": prefix}],
             remappings=[("joint_states", "display_joint_states"),
                         ("/tf", "tf"), ("/tf_static", "tf_static")]),
        Node(package="rviz2", executable="rviz2", namespace=namespace,
             arguments=["-d", rviz_path],
             remappings=[("/tf", "tf"), ("/tf_static", "tf_static")],
             condition=IfCondition(LaunchConfiguration("gui"))),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("product_id", description="Required engraved MILLY ID"),
        DeclareLaunchArgument("gui", default_value="true", choices=["true", "false"]),
        OpaqueFunction(function=setup),
    ])
