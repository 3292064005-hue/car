cmake_minimum_required(VERSION 3.8)
project(robot_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ChassisState.msg"
  "msg/PowerState.msg"
  "msg/VisionTarget.msg"
  "msg/VoiceCommand.msg"
  "msg/Fault.msg"
  "msg/ModeState.msg"
  "msg/SystemStatus.msg"
  "msg/EventLog.msg"
  "msg/SpeakRequest.msg"
  "srv/SetMode.srv"
  "srv/ResetFault.srv"
  "srv/TriggerSpeak.srv"
  "srv/SaveSnapshot.srv"
  "action/StartPatrol.action"
  "action/TrackTarget.action"
  "action/SaveSnapshotTask.action"
  DEPENDENCIES builtin_interfaces std_msgs geometry_msgs sensor_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
