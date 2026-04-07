from launch import LaunchDescription

from robot_bringup.launch_common import common_arguments, standard_nodes


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(common_arguments(profile_name='demo') + standard_nodes(include_voice=True, include_vision=True, include_monitor=True, include_teleop=False, include_web_bridge=True))
