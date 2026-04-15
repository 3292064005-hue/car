from __future__ import annotations

import os
from pathlib import Path

import yaml
from typing import Iterable

from launch.actions import DeclareLaunchArgument, EmitEvent, ExecuteProcess, LogInfo, OpaqueFunction, RegisterEventHandler, SetLaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node

from robot_contracts.lane_registry import hardware_lane_entry, navigation_lane_entry
from robot_bringup.config_resolution import CONFIG_PATH_INPUT_ENV, resolve_bringup_config
from robot_bringup.launch_profiles import launch_argument_defaults
from robot_bridge.runtime_factory import (
    DEFAULT_BRIDGE_RUNTIME_MODE,
    LEGACY_MONOLITH_RUNTIME_LABEL,
    SPLIT_RUNTIME_LABEL,
    normalize_bridge_runtime_mode,
)


AUTO_PROFILE_VALUE = '__PROFILE_AUTO__'
STARTUP_BARRIER_TIMEOUT_SEC = '20.0'
STARTUP_BARRIER_POLL_INTERVAL_SEC = '0.25'


def _bool_arg(value: bool) -> str:
    return 'true' if value else 'false'


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _resolved_runtime_config(profile_name: str):
    override = os.environ.get(CONFIG_PATH_INPUT_ENV)
    resolved = resolve_bringup_config(override)
    defaults = launch_argument_defaults(profile_name, config_path=override)
    return resolved, defaults


def _profile_defaults_setup(context, *, profile_name: str):
    """Late-bind profile defaults after launch arguments are resolved.

    Args:
        context: Launch runtime context.
        profile_name: Launch profile name associated with the current launch file.

    Returns:
        Launch actions that materialize profile-derived defaults for arguments still
        carrying the auto-resolution sentinel.

    Raises:
        None.
    """
    config_root = str(LaunchConfiguration('config_root').perform(context))
    launch_profiles_path = str(LaunchConfiguration('launch_profiles_path').perform(context))
    defaults = launch_argument_defaults(profile_name, config_path=config_root, launch_profiles_path=launch_profiles_path)
    actions = []
    for key, value in defaults.items():
        if str(LaunchConfiguration(key).perform(context)) == AUTO_PROFILE_VALUE:
            actions.append(SetLaunchConfiguration(key, value))
    return actions


def _launch_arg_truthy(context, name: str, *, default: bool = False) -> bool:
    """Resolve one launch argument into a boolean value.

    Args:
        context: Launch runtime context.
        name: Launch argument name.
        default: Fallback value when the launch argument is absent.

    Returns:
        Boolean interpretation of the launch argument.

    Raises:
        None.
    """
    try:
        raw = str(LaunchConfiguration(name).perform(context) or '').strip().lower()
    except Exception:
        return bool(default)
    if not raw:
        return bool(default)
    return raw in {'1', 'true', 'yes', 'on'}



def _bridge_runtime_setup(context):
    """Resolve bridge runtime mode and rollback-only compatibility gating.

    Args:
        context: Launch runtime context.

    Returns:
        Launch actions that normalize runtime compatibility arguments.

    Raises:
        None. Invalid legacy selections are converted into launch shutdown actions.

    Boundary behavior:
        ``bridge_runtime_split`` is no longer a public launch argument. The
        launch graph derives its internal split/legacy boolean solely from the
        authoritative ``bridge_runtime_mode`` selection so the default launch
        surface exposes one mainline runtime plus one explicit rollback gate.
    """
    requested_mode = str(LaunchConfiguration('bridge_runtime_mode').perform(context) or '').strip()
    legacy_allowed = _launch_arg_truthy(context, 'allow_legacy_bridge_runtime', default=False)
    try:
        mode = normalize_bridge_runtime_mode(requested_mode, allow_legacy=legacy_allowed)
    except ValueError as exc:
        return [
            LogInfo(msg=f'robot_bringup legacy runtime selection rejected: {exc}'),
            EmitEvent(event=Shutdown(reason=str(exc))),
        ]
    return [
        SetLaunchConfiguration('bridge_runtime_mode', mode),
        SetLaunchConfiguration('bridge_runtime_split', _bool_arg(mode == SPLIT_RUNTIME_LABEL)),
        LogInfo(msg=f'robot_bringup bridge_runtime_mode={mode}'),
        LogInfo(
            msg='robot_bringup legacy runtime selected through the explicit rollback gate',
            condition=UnlessCondition(LaunchConfiguration('bridge_runtime_split')),
        ),
    ]


def _launch_arg_value(context, name: str, *, default: str = '') -> str:
    """Resolve one launch argument into a stripped string value."""
    try:
        value = LaunchConfiguration(name).perform(context)
    except Exception:
        return default
    normalized = str(value or '').strip()
    if not normalized or normalized == AUTO_PROFILE_VALUE:
        return default
    return normalized




def _load_ros_parameters_file(path_value: str, *, root_key: str) -> dict[str, object]:
    """Load one ROS parameter YAML file and return its ``ros__parameters`` block.

    Args:
        path_value: Absolute or relative YAML path.
        root_key: Top-level node key expected in the YAML file.

    Returns:
        Parameter mapping. Missing or malformed files yield an empty mapping.

    Raises:
        None.
    """
    source = Path(str(path_value or '').strip())
    if not source.is_file():
        return {}
    payload = yaml.safe_load(source.read_text(encoding='utf-8')) or {}
    config = payload.get(root_key, payload) if isinstance(payload, dict) else {}
    ros_params = config.get('ros__parameters', {}) if isinstance(config, dict) and isinstance(config.get('ros__parameters', {}), dict) else {}
    return dict(ros_params)



def _resolve_navigation_runtime_launch_spec(context) -> dict[str, str]:
    """Resolve the navigation runtime package/executable/child factory.

    The provider contract remains authoritative; launch-time selection only maps
    that provider to the lane package declared in the lane registry.
    """
    navigation_config_path = _launch_arg_value(context, 'navigation_config_path')
    params = _load_ros_parameters_file(navigation_config_path, root_key='robot_navigation')
    provider_name = str(params.get('provider_name', 'simple_nav_provider') or 'simple_nav_provider').strip() or 'simple_nav_provider'
    lane = navigation_lane_entry(provider_name)
    return {
        'provider_name': provider_name,
        'package': lane.package_name,
        'executable': lane.executable,
        'child_factory': lane.child_factory,
        'node_name': 'robot_navigation',
    }



def _resolve_hardware_runtime_launch_spec(context) -> dict[str, str]:
    """Resolve the hardware runtime lane selected by the hardware config.

    Returns a dictionary describing the lane package and whether bridge runtime
    remains responsible for board transport topics.
    """
    hardware_config_path = _launch_arg_value(context, 'hardware_interface_config_path')
    params = _load_ros_parameters_file(hardware_config_path, root_key='robot_hardware_interface')
    role = str(params.get('compatibility_surface_role', 'ros_projection_only') or 'ros_projection_only').strip() or 'ros_projection_only'
    command_transport = str(params.get('command_transport', 'tcp_json_bridge') or 'tcp_json_bridge').strip() or 'tcp_json_bridge'
    lane = hardware_lane_entry(role)
    direct_driver_active = role == 'direct_driver' and command_transport == 'direct_driver_loop'
    return {
        'role': role,
        'command_transport': command_transport,
        'package': lane.package_name if direct_driver_active else hardware_lane_entry('ros_projection_only').package_name,
        'executable': lane.executable if direct_driver_active else hardware_lane_entry('ros_projection_only').executable,
        'child_factory': lane.child_factory if direct_driver_active else hardware_lane_entry('ros_projection_only').child_factory,
        'node_name': 'robot_direct_driver' if direct_driver_active else 'robot_hardware_interface',
        'bridge_runtime_active': _bool_arg(not direct_driver_active),
        'direct_driver_active': _bool_arg(direct_driver_active),
    }



def _runtime_component_setup(context):
    """Set launch configurations for config-driven runtime lane selection.

    Args:
        context: Launch runtime context.

    Returns:
        Launch configuration update actions.

    Raises:
        None.
    """
    navigation_spec = _resolve_navigation_runtime_launch_spec(context)
    hardware_spec = _resolve_hardware_runtime_launch_spec(context)
    return [
        SetLaunchConfiguration('navigation_runtime_package', navigation_spec['package']),
        SetLaunchConfiguration('navigation_runtime_executable', navigation_spec['executable']),
        SetLaunchConfiguration('navigation_runtime_child_factory', navigation_spec['child_factory']),
        SetLaunchConfiguration('navigation_runtime_node_name', navigation_spec['node_name']),
        SetLaunchConfiguration('hardware_runtime_package', hardware_spec['package']),
        SetLaunchConfiguration('hardware_runtime_executable', hardware_spec['executable']),
        SetLaunchConfiguration('hardware_runtime_child_factory', hardware_spec['child_factory']),
        SetLaunchConfiguration('hardware_runtime_node_name', hardware_spec['node_name']),
        SetLaunchConfiguration('bridge_runtime_active', hardware_spec['bridge_runtime_active']),
        SetLaunchConfiguration('direct_driver_active', hardware_spec['direct_driver_active']),
    ]


def _operator_surface_http_contract(context) -> tuple[list[str], list[str]]:
    """Return operator-surface HTTP probe URLs and required ready fields."""
    if not _launch_arg_truthy(context, 'enable_api_server', default=False):
        return [], []
    probe_host = (
        _launch_arg_value(context, 'api_server_public_host')
        or _launch_arg_value(context, 'api_server_listen_host')
        or _launch_arg_value(context, 'websocket_public_host')
        or _launch_arg_value(context, 'bridge_host', default='127.0.0.1')
        or '127.0.0.1'
    )
    if probe_host in {'0.0.0.0', '::', '::0', '*'}:
        probe_host = '127.0.0.1'
    api_port = _launch_arg_value(context, 'api_server_port', default='9100')
    api_prefix = _launch_arg_value(context, 'api_server_api_prefix', default='/api/v1') or '/api/v1'
    if not api_prefix.startswith('/'):
        api_prefix = '/' + api_prefix.lstrip('/')
    return [f'http://{probe_host}:{api_port}{api_prefix}/health'], ['ok', 'operatorSurfaceReady']


def common_arguments(*, profile_name: str):
    """Build common bringup launch arguments.

    Args:
        profile_name: Launch profile bound to the current launch file.

    Returns:
        List of launch actions used by all system launch descriptions.

    Raises:
        None.
    """
    resolved, _defaults = _resolved_runtime_config(profile_name)
    config_root_default = str(resolved.config_root)
    return [
        DeclareLaunchArgument('config_root', default_value=config_root_default),
        DeclareLaunchArgument('launch_profiles_path', default_value=PathJoinSubstitution([LaunchConfiguration('config_root'), 'launch_profiles.yaml'])),
        DeclareLaunchArgument('log_level', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_voice', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_vision', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_monitor', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_teleop', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_localization', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_navigation', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_hardware_interface', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_api_server', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_ros_lifecycle_manager', default_value='true'),
        DeclareLaunchArgument('use_mock_robot', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_debug_overlay', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('diagnostics_enabled', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_web_bridge', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('bridge_host', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('bridge_port', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('mjpeg_url', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('websocket_public_host', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('websocket_listen_host', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('websocket_port', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('websocket_path', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('api_server_public_host', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('api_server_listen_host', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('api_server_port', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('api_server_ws_path', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('api_server_api_prefix', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('api_server_upstream_host', default_value='127.0.0.1'),
        DeclareLaunchArgument('description_path', default_value=config_root_default + '/description.yaml'),
        DeclareLaunchArgument('localization_config_path', default_value=config_root_default + '/localization.yaml'),
        DeclareLaunchArgument('navigation_config_path', default_value=config_root_default + '/navigation.yaml'),
        DeclareLaunchArgument('waypoint_config_path', default_value=config_root_default + '/waypoints.yaml'),
        DeclareLaunchArgument('hardware_interface_config_path', default_value=config_root_default + '/hardware_interface.yaml'),
        DeclareLaunchArgument('navigation_runtime_package', default_value='robot_navigation'),
        DeclareLaunchArgument('navigation_runtime_executable', default_value='navigation_node'),
        DeclareLaunchArgument('navigation_runtime_child_factory', default_value='robot_navigation.navigation_node:RobotNavigationNode'),
        DeclareLaunchArgument('navigation_runtime_node_name', default_value='robot_navigation'),
        DeclareLaunchArgument('hardware_runtime_package', default_value='robot_hardware_interface'),
        DeclareLaunchArgument('hardware_runtime_executable', default_value='hardware_interface_node'),
        DeclareLaunchArgument('hardware_runtime_child_factory', default_value='robot_hardware_interface.hardware_interface_node:RobotHardwareInterfaceNode'),
        DeclareLaunchArgument('hardware_runtime_node_name', default_value='robot_hardware_interface'),
        DeclareLaunchArgument('bridge_runtime_active', default_value='true'),
        DeclareLaunchArgument('direct_driver_active', default_value='false'),
        DeclareLaunchArgument('simulator_config_path', default_value=config_root_default + '/simulator.yaml'),
        DeclareLaunchArgument('api_server_config_path', default_value=config_root_default + '/api_server.yaml'),
        DeclareLaunchArgument('lifecycle_manager_config_path', default_value=config_root_default + '/lifecycle_manager.yaml'),
        DeclareLaunchArgument('bridge_runtime_mode', default_value=DEFAULT_BRIDGE_RUNTIME_MODE),
        DeclareLaunchArgument('allow_legacy_bridge_runtime', default_value='false'),
        DeclareLaunchArgument('startup_barrier_timeout_sec', default_value=STARTUP_BARRIER_TIMEOUT_SEC),
        DeclareLaunchArgument('startup_barrier_poll_interval_sec', default_value=STARTUP_BARRIER_POLL_INTERVAL_SEC),
        OpaqueFunction(function=lambda context: _profile_defaults_setup(context, profile_name=profile_name)),
        DeclareLaunchArgument('use_fault_profile', default_value='true'),
        OpaqueFunction(function=_bridge_runtime_setup),
        OpaqueFunction(function=_runtime_component_setup),
        LogInfo(msg=['robot_bringup config_root=', LaunchConfiguration('config_root')]),
        LogInfo(msg=['robot_bringup launch_profiles_path=', LaunchConfiguration('launch_profiles_path')]),
    ]


def config_path(name: str):
    """Build one runtime config file path from the effective config root.

    Args:
        name: Bringup YAML filename.

    Returns:
        Launch substitution resolving to the runtime config file path.

    Raises:
        None.
    """
    return PathJoinSubstitution([LaunchConfiguration('config_root'), name])


def _mock_robot_process(log_level: LaunchConfiguration):
    script = str((_workspace_root() / 'tools' / 'tcp_mock_robot.py').resolve())
    return ExecuteProcess(
        cmd=['python3', script, '--host', LaunchConfiguration('bridge_host'), '--port', LaunchConfiguration('bridge_port')],
        output='screen',
        name='inspection_mock_robot',
        shell=False,
        additional_env={'PYTHONUNBUFFERED': '1', 'ROBOT_LOG_LEVEL': log_level},
        condition=IfCondition(PythonExpression([LaunchConfiguration('use_mock_robot'), ' and ', LaunchConfiguration('bridge_runtime_active')])),
    )


def _startup_barrier_action(*, label: str, expected_nodes: Iterable[str], expected_topics: Iterable[str] = (), expected_services: Iterable[str] = (), expected_actions: Iterable[str] = (), expected_node_groups: Iterable[Iterable[str]] = (), expected_ready_topics: Iterable[str] = (), expected_http_urls: Iterable[str] = (), expected_http_ready_fields: Iterable[str] = ()) -> ExecuteProcess:
    script_cmd = ['python3', '-m', 'robot_bringup.startup_barrier', '--label', label, '--timeout-sec', LaunchConfiguration('startup_barrier_timeout_sec'), '--poll-interval-sec', LaunchConfiguration('startup_barrier_poll_interval_sec')]
    for node_name in expected_nodes:
        script_cmd.extend(['--expected-node', node_name])
    for node_group in expected_node_groups:
        group_value = ','.join(str(item) for item in node_group if str(item).strip())
        if group_value:
            script_cmd.extend(['--expected-node-group', group_value])
    for topic_name in expected_topics:
        script_cmd.extend(['--expected-topic', topic_name])
    for ready_topic_name in expected_ready_topics:
        script_cmd.extend(['--expected-ready-topic', ready_topic_name])
    for http_url in expected_http_urls:
        script_cmd.extend(['--expected-http-url', http_url])
    for http_ready_field in expected_http_ready_fields:
        script_cmd.extend(['--expected-http-ready-field', http_ready_field])
    for service_name in expected_services:
        script_cmd.extend(['--expected-service', service_name])
    for action_name in expected_actions:
        script_cmd.extend(['--expected-action', action_name])
    return ExecuteProcess(cmd=script_cmd, output='screen', shell=False, name=f'{label}_startup_barrier')


def _chain_barrier(*, barrier: ExecuteProcess, on_success: list, failure_reason: str) -> list:
    def _on_exit(_context, event, *, success_actions: list, reason: str):
        return_code = getattr(event, 'returncode', None)
        if return_code == 0:
            return success_actions
        return [LogInfo(msg=f'robot_bringup startup barrier failed: {reason}; returncode={return_code}'), EmitEvent(event=Shutdown(reason=reason))]

    return [
        barrier,
        RegisterEventHandler(OnProcessExit(target_action=barrier, on_exit=[OpaqueFunction(function=lambda context, event, success_actions=on_success, reason=failure_reason: _on_exit(context, event, success_actions=success_actions, reason=reason))])),
    ]


def _resolve_control_barrier_requirements(context, *, include_monitor: bool, include_voice: bool, include_vision: bool, include_navigation: bool = True) -> dict[str, list[str]]:
    """Resolve control-phase readiness requirements after launch arguments are known.

    Args:
        context: Launch runtime context.
        include_monitor: Whether the current profile can include the monitor node.
        include_voice: Whether the current profile can include the voice node.
        include_vision: Whether the current profile can include the vision node.
        include_navigation: Whether the current profile can include navigation.

    Returns:
        Mapping with ``nodes``, ``services``, and ``actions`` lists that must be ready
        before the lifecycle manager activates the decision/runtime stack.

    Raises:
        None.
    """
    lifecycle_managed = _launch_arg_truthy(context, 'enable_ros_lifecycle_manager', default=True)
    if lifecycle_managed:
        nodes = ['/robot_control_lifecycle', '/robot_decision_lifecycle']
        if include_navigation and _launch_arg_truthy(context, 'enable_navigation', default=True):
            nodes.append('/robot_navigation_lifecycle')
    else:
        nodes = ['/robot_control', '/robot_decision']
        if include_navigation and _launch_arg_truthy(context, 'enable_navigation', default=True):
            nodes.append('/robot_navigation')
    requirements = {'nodes': nodes, 'services': [], 'actions': []}
    if include_monitor and _launch_arg_truthy(context, 'enable_monitor', default=True):
        requirements['nodes'].append('/robot_monitor')
    if include_voice and _launch_arg_truthy(context, 'enable_voice', default=True):
        requirements['nodes'].append('/robot_voice')
    if include_vision and _launch_arg_truthy(context, 'enable_vision', default=True):
        requirements['nodes'].append('/robot_vision')
        requirements['services'].append('/robot/save_snapshot')
        requirements['actions'].append('/robot/actions/save_snapshot')
    return requirements



def standard_nodes(*, include_voice: bool, include_vision: bool, include_monitor: bool, include_teleop: bool, include_web_bridge: bool = True):
    decision_params = [config_path('decision.yaml')]
    control_params = [config_path('control.yaml')]
    localization_params = [LaunchConfiguration('localization_config_path'), {'description_path': LaunchConfiguration('description_path')}]
    navigation_params = [LaunchConfiguration('navigation_config_path'), {'route_plan_path': LaunchConfiguration('waypoint_config_path')}]
    hardware_interface_params = [LaunchConfiguration('hardware_interface_config_path'), {'description_path': LaunchConfiguration('description_path')}]
    bridge_params = [config_path('bridge.yaml'), {
        'host': LaunchConfiguration('bridge_host'),
        'port': LaunchConfiguration('bridge_port'),
    }]
    fault_params = config_path('fault.yaml')
    log_level = LaunchConfiguration('log_level')
    diagnostics_enabled = LaunchConfiguration('diagnostics_enabled')
    debug_overlay_enabled = LaunchConfiguration('enable_debug_overlay')

    bridge_node = Node(package='robot_bridge', executable='bridge_node', name='robot_bridge', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(PythonExpression([LaunchConfiguration('bridge_runtime_active'), ' and not ', LaunchConfiguration('bridge_runtime_split')])))
    bridge_transport_node = Node(package='robot_bridge', executable='bridge_transport_node', name='robot_bridge_transport', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(PythonExpression([LaunchConfiguration('bridge_runtime_active'), ' and ', LaunchConfiguration('bridge_runtime_split')])))
    bridge_protocol_node = Node(package='robot_bridge', executable='bridge_protocol_node', name='robot_bridge_protocol', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(PythonExpression([LaunchConfiguration('bridge_runtime_active'), ' and ', LaunchConfiguration('bridge_runtime_split')])))
    bridge_projection_node = Node(package='robot_bridge', executable='bridge_projection_node', name='robot_bridge_projection', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(PythonExpression([LaunchConfiguration('bridge_runtime_active'), ' and ', LaunchConfiguration('bridge_runtime_split')])))
    bridge_health_node = Node(package='robot_bridge', executable='bridge_health_node', name='robot_bridge_health', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(PythonExpression([LaunchConfiguration('bridge_runtime_active'), ' and ', LaunchConfiguration('bridge_runtime_split')])))
    control_node = Node(package='robot_control', executable='control_node', name='robot_control', parameters=control_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=UnlessCondition(LaunchConfiguration('enable_ros_lifecycle_manager')))
    control_lifecycle_node = Node(package='robot_bringup', executable='managed_component_node', name='robot_control_lifecycle', parameters=[{'component_id': 'robot_control', 'child_factory': 'robot_control.control_node:ControlNode', 'child_node_name': 'robot_control', 'executor_threads': 1, 'bond_topic': '/bond', 'status_topic': '/robot/lifecycle/robot_control/status'}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_ros_lifecycle_manager')))
    monitor_node = None
    if include_monitor:
        monitor_node = Node(package='robot_monitor', executable='monitor_node', name='robot_monitor', parameters=[config_path('monitor.yaml'), {'diagnostics_enabled': diagnostics_enabled}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_monitor')))
    voice_node = None
    if include_voice:
        voice_node = Node(package='robot_voice', executable='voice_node', name='robot_voice', parameters=[config_path('voice.yaml')], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_voice')))
    vision_node = None
    if include_vision:
        vision_node = Node(package='robot_vision', executable='vision_node', name='robot_vision', parameters=[config_path('vision.yaml'), {'color_profile_path': config_path('color_profiles.yaml'), 'enable_debug_overlay': debug_overlay_enabled, 'stream_url': LaunchConfiguration('mjpeg_url'), 'mjpeg_url': LaunchConfiguration('mjpeg_url')}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_vision')))
    decision_node = Node(package='robot_decision', executable='decision_node', name='robot_decision', parameters=decision_params, arguments=['--ros-args', '--log-level', log_level], output='screen', condition=UnlessCondition(LaunchConfiguration('enable_ros_lifecycle_manager')))
    decision_lifecycle_node = Node(package='robot_bringup', executable='managed_component_node', name='robot_decision_lifecycle', parameters=[{'component_id': 'robot_decision', 'child_factory': 'robot_decision.decision_node:DecisionNode', 'child_node_name': 'robot_decision', 'executor_threads': 4, 'bond_topic': '/bond', 'status_topic': '/robot/lifecycle/robot_decision/status'}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_ros_lifecycle_manager')))
    localization_node = Node(package='robot_localization', executable='localization_node', name='robot_localization', parameters=localization_params, arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_localization')))
    navigation_node = Node(package=LaunchConfiguration('navigation_runtime_package'), executable=LaunchConfiguration('navigation_runtime_executable'), name=LaunchConfiguration('navigation_runtime_node_name'), parameters=navigation_params, arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(PythonExpression([LaunchConfiguration('enable_navigation'), ' and not ', LaunchConfiguration('enable_ros_lifecycle_manager')])))
    navigation_lifecycle_node = Node(package='robot_bringup', executable='managed_component_node', name='robot_navigation_lifecycle', parameters=[{'component_id': 'robot_navigation', 'child_factory': LaunchConfiguration('navigation_runtime_child_factory'), 'child_node_name': LaunchConfiguration('navigation_runtime_node_name'), 'executor_threads': 1, 'bond_topic': '/bond', 'status_topic': '/robot/lifecycle/robot_navigation/status'}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(PythonExpression([LaunchConfiguration('enable_navigation'), ' and ', LaunchConfiguration('enable_ros_lifecycle_manager')])))
    hardware_interface_node = Node(package=LaunchConfiguration('hardware_runtime_package'), executable=LaunchConfiguration('hardware_runtime_executable'), name=LaunchConfiguration('hardware_runtime_node_name'), parameters=hardware_interface_params, arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_hardware_interface')))
    teleop_node = None
    if include_teleop:
        teleop_node = Node(package='robot_teleop', executable='keyboard_teleop', name='robot_keyboard_teleop', parameters=[config_path('teleop.yaml')], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_teleop')))
    web_bridge_node = None
    if include_web_bridge:
        web_bridge_node = Node(package='robot_web_bridge', executable='web_bridge_node', name='robot_web_bridge', parameters=[{'mjpeg_url': LaunchConfiguration('mjpeg_url'), 'listen_host': LaunchConfiguration('websocket_listen_host'), 'listen_port': LaunchConfiguration('websocket_port'), 'ws_path': LaunchConfiguration('websocket_path'), 'runtime_param_require_monitor_ack': LaunchConfiguration('enable_monitor'), 'operator_ready_topic': '/robot/web_bridge/ready', 'internal_command_socket_path': os.environ.get('ROBOT_INTERNAL_COMMAND_SOCKET_PATH', '/tmp/inspection_robot/bridge_internal_command.sock'), 'internal_command_auth_token': os.environ.get('ROBOT_INTERNAL_COMMAND_AUTH_TOKEN', '')}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_web_bridge')))
    api_server_process = ExecuteProcess(
        cmd=[
            'python3', '-m', 'robot_api_server.api_server_main',
            '--config-file', LaunchConfiguration('api_server_config_path'),
            '--listen-host', LaunchConfiguration('api_server_listen_host'),
            '--listen-port', LaunchConfiguration('api_server_port'),
            '--ws-path', LaunchConfiguration('api_server_ws_path'),
            '--api-prefix', LaunchConfiguration('api_server_api_prefix'),
            '--upstream-url', ['ws://', LaunchConfiguration('api_server_upstream_host'), ':', LaunchConfiguration('websocket_port'), LaunchConfiguration('websocket_path')],
            '--internal-command-socket-path', os.environ.get('ROBOT_INTERNAL_COMMAND_SOCKET_PATH', '/tmp/inspection_robot/bridge_internal_command.sock'),
            '--internal-command-auth-token', os.environ.get('ROBOT_INTERNAL_COMMAND_AUTH_TOKEN', ''),
        ],
        output='screen',
        shell=False,
        name='robot_api_server',
        additional_env={'PYTHONUNBUFFERED': '1'},
        condition=IfCondition(LaunchConfiguration('enable_api_server')),
    )

    phase0 = [
        _mock_robot_process(log_level),
        bridge_node,
        bridge_transport_node,
        bridge_protocol_node,
        bridge_projection_node,
        bridge_health_node,
    ]
    lifecycle_manager_node = Node(package='robot_bringup', executable='ros_lifecycle_manager', name='robot_lifecycle_manager', parameters=[LaunchConfiguration('lifecycle_manager_config_path'), {'managed_nodes': ['robot_control_lifecycle', 'robot_navigation_lifecycle', 'robot_decision_lifecycle'], 'optional_managed_nodes': ['robot_navigation_lifecycle']}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_ros_lifecycle_manager')))

    phase1 = [control_node, control_lifecycle_node, monitor_node, voice_node, vision_node, hardware_interface_node, localization_node, navigation_node, navigation_lifecycle_node, decision_node, decision_lifecycle_node]
    phase2 = [lifecycle_manager_node]
    phase3 = [teleop_node, web_bridge_node, api_server_process]

    bridge_barrier_nodes: list[str] = []
    bridge_barrier_groups = [
        ['/robot_bridge'],
        ['/robot_bridge_transport', '/robot_bridge_protocol', '/robot_bridge_projection', '/robot_bridge_health'],
    ]

    bridge_barrier = _startup_barrier_action(label='bridge_phase', expected_nodes=bridge_barrier_nodes, expected_node_groups=bridge_barrier_groups)

    def _barrier_chain_setup(context):
        control_requirements = _resolve_control_barrier_requirements(context, include_monitor=include_monitor, include_voice=include_voice, include_vision=include_vision, include_navigation=True)
        control_barrier = _startup_barrier_action(
            label='control_phase',
            expected_nodes=control_requirements['nodes'],
            expected_services=control_requirements['services'],
            expected_actions=control_requirements['actions'],
        )

        decision_nodes = ['/robot_decision', '/robot_control']
        if _launch_arg_truthy(context, 'enable_navigation', default=True):
            decision_nodes.append('/robot_navigation')
        decision_ready_topics = []
        if _launch_arg_truthy(context, 'enable_ros_lifecycle_manager', default=True):
            decision_ready_topics.append('/robot/lifecycle_manager/ready')
        decision_barrier = _startup_barrier_action(
            label='decision_phase',
            expected_nodes=decision_nodes,
            expected_topics=['/robot/decision/summary'],
            expected_ready_topics=decision_ready_topics,
            expected_services=['/robot/set_mode', '/robot/reset_fault'],
            expected_actions=['/robot/actions/start_patrol', '/robot/actions/track_target'],
        )

        operator_barrier_actions: list = []
        if include_web_bridge and _launch_arg_truthy(context, 'enable_web_bridge', default=True):
            operator_http_urls, operator_http_ready_fields = _operator_surface_http_contract(context)
            operator_barrier = _startup_barrier_action(
                label='operator_phase',
                expected_nodes=['/robot_web_bridge'],
                expected_ready_topics=['/robot/web_bridge/ready'],
                expected_http_urls=operator_http_urls,
                expected_http_ready_fields=operator_http_ready_fields,
            )
            operator_barrier_actions = _chain_barrier(
                barrier=operator_barrier,
                on_success=[],
                failure_reason='operator readiness barrier failed',
            )

        return _chain_barrier(
            barrier=bridge_barrier,
            on_success=[action for action in phase1 if action is not None]
            + _chain_barrier(
                barrier=control_barrier,
                on_success=[action for action in phase2 if action is not None]
                + _chain_barrier(
                    barrier=decision_barrier,
                    on_success=[action for action in phase3 if action is not None] + operator_barrier_actions,
                    failure_reason='decision readiness barrier failed',
                ),
                failure_reason='control readiness barrier failed',
            ),
            failure_reason='bridge readiness barrier failed',
        )

    startup_actions = [action for action in phase0 if action is not None]
    startup_actions.append(OpaqueFunction(function=lambda context: _barrier_chain_setup(context)))
    return startup_actions
