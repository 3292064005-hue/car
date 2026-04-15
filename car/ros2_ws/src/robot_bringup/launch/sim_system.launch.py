from launch import LaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import ExecuteProcess

from robot_bringup.launch_common import common_arguments, config_path


def generate_launch_description() -> LaunchDescription:
    log_level = LaunchConfiguration('log_level')
    nodes = [
        Node(package='robot_simulator', executable='simulator_node', name='robot_simulator', parameters=[config_path('simulator.yaml')], arguments=['--ros-args', '--log-level', log_level], output='screen'),
        Node(package='robot_control', executable='control_node', name='robot_control', parameters=[config_path('control.yaml'), config_path('fault.yaml')], arguments=['--ros-args', '--log-level', log_level], output='screen'),
        Node(package='robot_monitor', executable='monitor_node', name='robot_monitor', parameters=[config_path('monitor.yaml'), {'diagnostics_enabled': LaunchConfiguration('diagnostics_enabled')}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_monitor'))),
        Node(package='robot_voice', executable='voice_node', name='robot_voice', parameters=[config_path('voice.yaml')], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_voice'))),
        Node(package='robot_vision', executable='vision_node', name='robot_vision', parameters=[config_path('vision.yaml'), {'color_profile_path': config_path('color_profiles.yaml'), 'enable_debug_overlay': LaunchConfiguration('enable_debug_overlay'), 'stream_url': LaunchConfiguration('mjpeg_url'), 'mjpeg_url': LaunchConfiguration('mjpeg_url')}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_vision'))),
        Node(package='robot_decision', executable='decision_node', name='robot_decision', parameters=[config_path('decision.yaml')], arguments=['--ros-args', '--log-level', log_level], output='screen'),
        Node(package='robot_teleop', executable='keyboard_teleop', name='robot_keyboard_teleop', parameters=[config_path('teleop.yaml')], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_teleop'))),
        Node(package='robot_web_bridge', executable='web_bridge_node', name='robot_web_bridge', parameters=[{'mjpeg_url': LaunchConfiguration('mjpeg_url'), 'listen_host': LaunchConfiguration('websocket_listen_host'), 'listen_port': LaunchConfiguration('websocket_port'), 'ws_path': LaunchConfiguration('websocket_path'), 'runtime_param_require_monitor_ack': LaunchConfiguration('enable_monitor'), 'operator_ready_topic': '/robot/web_bridge/ready'}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_web_bridge'))),
        Node(package='robot_localization', executable='localization_node', name='robot_localization', parameters=[LaunchConfiguration('localization_config_path'), {'description_path': LaunchConfiguration('description_path')}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_localization'))),
        Node(package='robot_navigation', executable='navigation_node', name='robot_navigation', parameters=[LaunchConfiguration('navigation_config_path'), {'route_plan_path': LaunchConfiguration('waypoint_config_path')}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_navigation'))),
        Node(package='robot_hardware_interface', executable='hardware_interface_node', name='robot_hardware_interface', parameters=[LaunchConfiguration('hardware_interface_config_path'), {'description_path': LaunchConfiguration('description_path'), 'hardware_interface_config_path': LaunchConfiguration('hardware_interface_config_path')}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_hardware_interface'))),
        ExecuteProcess(
            cmd=['python3', '-m', 'robot_api_server.api_server_main', '--config-file', LaunchConfiguration('api_server_config_path'), '--listen-host', LaunchConfiguration('api_server_listen_host'), '--listen-port', LaunchConfiguration('api_server_port'), '--ws-path', LaunchConfiguration('api_server_ws_path'), '--api-prefix', LaunchConfiguration('api_server_api_prefix'), '--upstream-url', ['ws://', LaunchConfiguration('api_server_upstream_host'), ':', LaunchConfiguration('websocket_port'), LaunchConfiguration('websocket_path')]],
            output='screen',
            shell=False,
            name='robot_api_server',
            additional_env={'PYTHONUNBUFFERED': '1'},
            condition=IfCondition(LaunchConfiguration('enable_api_server')),
        ),
    ]
    return LaunchDescription(common_arguments(profile_name='sim') + nodes)
