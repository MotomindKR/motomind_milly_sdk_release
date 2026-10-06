cmake_minimum_required(VERSION 3.16)
project(milly_sdk_interfaces)
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MitCommand.msg" "msg/MotorState.msg" "msg/MotorStates.msg" "msg/DriverStatus.msg"
  "srv/MoveJ.srv" "srv/MoveP.srv" "srv/Gripper.srv" "srv/FloatMode.srv"
  "srv/SetMaxVel.srv" "srv/SetGains.srv" "srv/GetRobotInfo.srv" "srv/Fk.srv"
  DEPENDENCIES std_msgs)
ament_export_dependencies(rosidl_default_runtime)
ament_package()
