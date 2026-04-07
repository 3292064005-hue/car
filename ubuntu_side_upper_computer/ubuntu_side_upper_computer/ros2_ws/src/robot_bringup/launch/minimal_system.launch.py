from launch import LaunchDescription

from robot_bringup.launch_common import common_arguments, standard_nodes


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(common_arguments(profile_name='minimal') + standard_nodes(include_voice=False, include_vision=False, include_monitor=False, include_teleop=False, include_web_bridge=False))
