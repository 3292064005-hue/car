from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from launch.actions import DeclareLaunchArgument, EmitEvent, ExecuteProcess, LogInfo, OpaqueFunction, RegisterEventHandler, SetLaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node

from robot_bringup.config_resolution import CONFIG_PATH_INPUT_ENV, resolve_bringup_config
from robot_bringup.launch_profiles import launch_argument_defaults
from robot_bridge.runtime_factory import (
    DEFAULT_BRIDGE_RUNTIME_MODE,
    DEFAULT_BRIDGE_RUNTIME_SPLIT,
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
    """Resolve bridge runtime mode and compatibility gating.

    Args:
        context: Launch runtime context.

    Returns:
        Launch actions that normalize runtime compatibility arguments.

    Raises:
        None. Invalid legacy selections are converted into launch shutdown actions.
    """
    requested_mode = str(LaunchConfiguration('bridge_runtime_mode').perform(context) or '').strip()
    legacy_allowed = _launch_arg_truthy(context, 'allow_legacy_bridge_runtime', default=False)
    compatibility_split = str(LaunchConfiguration('bridge_runtime_split').perform(context) or '').strip()
    compatibility_override = compatibility_split.lower() != _bool_arg(DEFAULT_BRIDGE_RUNTIME_SPLIT)
    if not requested_mode or (requested_mode == DEFAULT_BRIDGE_RUNTIME_MODE and compatibility_override):
        requested_mode = compatibility_split
    try:
        mode = normalize_bridge_runtime_mode(requested_mode, allow_legacy=legacy_allowed)
    except ValueError as exc:
        return [
            LogInfo(msg=f'robot_bringup legacy runtime selection rejected: {exc}'),
            EmitEvent(event=Shutdown(reason=str(exc))),
        ]
    actions = [
        SetLaunchConfiguration('bridge_runtime_mode', mode),
        SetLaunchConfiguration('bridge_runtime_split', _bool_arg(mode == SPLIT_RUNTIME_LABEL)),
        LogInfo(msg=f'robot_bringup bridge_runtime_mode={mode}'),
        LogInfo(
            msg='[deprecated] bridge_runtime_split is now compatibility-only; use bridge_runtime_mode and allow_legacy_bridge_runtime for rollback',
            condition=UnlessCondition(LaunchConfiguration('bridge_runtime_split')),
        ),
    ]
    if compatibility_override and requested_mode == compatibility_split:
        actions.append(LogInfo(msg='robot_bringup bridge_runtime_split compatibility override engaged'))
    return actions


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
    strict_profiles = {'full', 'hardware'}
    strict_patrol = profile_name in strict_profiles
    config_root_default = str(resolved.config_root)
    return [
        DeclareLaunchArgument('config_root', default_value=config_root_default),
        DeclareLaunchArgument('launch_profiles_path', default_value=PathJoinSubstitution([LaunchConfiguration('config_root'), 'launch_profiles.yaml'])),
        DeclareLaunchArgument('log_level', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_voice', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_vision', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_monitor', default_value=AUTO_PROFILE_VALUE),
        DeclareLaunchArgument('enable_teleop', default_value=AUTO_PROFILE_VALUE),
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
        DeclareLaunchArgument('bridge_runtime_mode', default_value=DEFAULT_BRIDGE_RUNTIME_MODE),
        DeclareLaunchArgument('allow_legacy_bridge_runtime', default_value='false'),
        DeclareLaunchArgument('startup_barrier_timeout_sec', default_value=STARTUP_BARRIER_TIMEOUT_SEC),
        DeclareLaunchArgument('startup_barrier_poll_interval_sec', default_value=STARTUP_BARRIER_POLL_INTERVAL_SEC),
        OpaqueFunction(function=lambda context: _profile_defaults_setup(context, profile_name=profile_name)),
        DeclareLaunchArgument('use_fault_profile', default_value='true'),
        DeclareLaunchArgument('bridge_runtime_split', default_value=_bool_arg(DEFAULT_BRIDGE_RUNTIME_SPLIT)),
        DeclareLaunchArgument('strict_patrol_config', default_value=_bool_arg(strict_patrol)),
        DeclareLaunchArgument('allow_default_patrol_fallback', default_value=_bool_arg(not strict_patrol)),
        OpaqueFunction(function=_bridge_runtime_setup),
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
        condition=IfCondition(LaunchConfiguration('use_mock_robot')),
    )


def _startup_barrier_action(*, label: str, expected_nodes: Iterable[str], expected_topics: Iterable[str] = (), expected_services: Iterable[str] = (), expected_actions: Iterable[str] = (), expected_node_groups: Iterable[Iterable[str]] = ()) -> ExecuteProcess:
    script_cmd = ['python3', '-m', 'robot_bringup.startup_barrier', '--label', label, '--timeout-sec', LaunchConfiguration('startup_barrier_timeout_sec'), '--poll-interval-sec', LaunchConfiguration('startup_barrier_poll_interval_sec')]
    for node_name in expected_nodes:
        script_cmd.extend(['--expected-node', node_name])
    for node_group in expected_node_groups:
        group_value = ','.join(str(item) for item in node_group if str(item).strip())
        if group_value:
            script_cmd.extend(['--expected-node-group', group_value])
    for topic_name in expected_topics:
        script_cmd.extend(['--expected-topic', topic_name])
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


def _resolve_control_barrier_requirements(context, *, include_monitor: bool, include_voice: bool, include_vision: bool) -> dict[str, list[str]]:
    """Resolve control-phase readiness requirements after launch arguments are known.

    Args:
        context: Launch runtime context.
        include_monitor: Whether the current profile can include the monitor node.
        include_voice: Whether the current profile can include the voice node.
        include_vision: Whether the current profile can include the vision node.

    Returns:
        Mapping with ``nodes``, ``services``, and ``actions`` lists that must be ready
        before the decision phase starts.

    Raises:
        None.
    """
    requirements = {'nodes': ['/robot_control'], 'services': [], 'actions': []}
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
    patrol_path = config_path('patrol.yaml')
    decision_params = [config_path('decision.yaml'), {
        'patrol_config_path': patrol_path,
        'strict_patrol_config': LaunchConfiguration('strict_patrol_config'),
        'allow_default_patrol_fallback': LaunchConfiguration('allow_default_patrol_fallback'),
    }]
    control_params = [config_path('control.yaml')]
    bridge_params = [config_path('bridge.yaml'), {
        'host': LaunchConfiguration('bridge_host'),
        'port': LaunchConfiguration('bridge_port'),
    }]
    fault_params = config_path('fault.yaml')
    log_level = LaunchConfiguration('log_level')
    diagnostics_enabled = LaunchConfiguration('diagnostics_enabled')
    debug_overlay_enabled = LaunchConfiguration('enable_debug_overlay')

    bridge_node = Node(package='robot_bridge', executable='bridge_node', name='robot_bridge', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=UnlessCondition(LaunchConfiguration('bridge_runtime_split')))
    bridge_transport_node = Node(package='robot_bridge', executable='bridge_transport_node', name='robot_bridge_transport', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('bridge_runtime_split')))
    bridge_protocol_node = Node(package='robot_bridge', executable='bridge_protocol_node', name='robot_bridge_protocol', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('bridge_runtime_split')))
    bridge_projection_node = Node(package='robot_bridge', executable='bridge_projection_node', name='robot_bridge_projection', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('bridge_runtime_split')))
    bridge_health_node = Node(package='robot_bridge', executable='bridge_health_node', name='robot_bridge_health', parameters=bridge_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('bridge_runtime_split')))
    control_node = Node(package='robot_control', executable='control_node', name='robot_control', parameters=control_params + [fault_params], arguments=['--ros-args', '--log-level', log_level], output='screen')
    monitor_node = None
    if include_monitor:
        monitor_node = Node(package='robot_monitor', executable='monitor_node', name='robot_monitor', parameters=[config_path('monitor.yaml'), {'diagnostics_enabled': diagnostics_enabled}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_monitor')))
    voice_node = None
    if include_voice:
        voice_node = Node(package='robot_voice', executable='voice_node', name='robot_voice', parameters=[config_path('voice.yaml')], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_voice')))
    vision_node = None
    if include_vision:
        vision_node = Node(package='robot_vision', executable='vision_node', name='robot_vision', parameters=[config_path('vision.yaml'), {'color_profile_path': config_path('color_profiles.yaml'), 'enable_debug_overlay': debug_overlay_enabled, 'stream_url': LaunchConfiguration('mjpeg_url'), 'mjpeg_url': LaunchConfiguration('mjpeg_url')}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_vision')))
    decision_node = Node(package='robot_decision', executable='decision_node', name='robot_decision', parameters=decision_params, arguments=['--ros-args', '--log-level', log_level], output='screen')
    teleop_node = None
    if include_teleop:
        teleop_node = Node(package='robot_teleop', executable='keyboard_teleop', name='robot_keyboard_teleop', parameters=[config_path('teleop.yaml')], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_teleop')))
    web_bridge_node = None
    if include_web_bridge:
        web_bridge_node = Node(package='robot_web_bridge', executable='web_bridge_node', name='robot_web_bridge', parameters=[{'mjpeg_url': LaunchConfiguration('mjpeg_url'), 'listen_host': LaunchConfiguration('websocket_listen_host'), 'listen_port': LaunchConfiguration('websocket_port'), 'ws_path': LaunchConfiguration('websocket_path')}], arguments=['--ros-args', '--log-level', log_level], output='screen', condition=IfCondition(LaunchConfiguration('enable_web_bridge')))

    phase0 = [
        _mock_robot_process(log_level),
        bridge_node,
        bridge_transport_node,
        bridge_protocol_node,
        bridge_projection_node,
        bridge_health_node,
    ]
    phase1 = [control_node, monitor_node, voice_node, vision_node]
    phase2 = [decision_node]
    phase3 = [teleop_node, web_bridge_node]

    bridge_barrier_nodes: list[str] = []
    bridge_barrier_groups = [
        ['/robot_bridge'],
        ['/robot_bridge_transport', '/robot_bridge_protocol', '/robot_bridge_projection', '/robot_bridge_health'],
    ]
    decision_barrier_nodes = ['/robot_decision']

    bridge_barrier = _startup_barrier_action(label='bridge_phase', expected_nodes=bridge_barrier_nodes, expected_node_groups=bridge_barrier_groups)
    decision_barrier = _startup_barrier_action(label='decision_phase', expected_nodes=decision_barrier_nodes, expected_topics=['/robot/decision/summary'], expected_services=['/robot/set_mode', '/robot/reset_fault'], expected_actions=['/robot/actions/start_patrol', '/robot/actions/track_target'])

    def _barrier_chain_setup(context):
        control_requirements = _resolve_control_barrier_requirements(context, include_monitor=include_monitor, include_voice=include_voice, include_vision=include_vision)
        control_barrier = _startup_barrier_action(
            label='control_phase',
            expected_nodes=control_requirements['nodes'],
            expected_services=control_requirements['services'],
            expected_actions=control_requirements['actions'],
        )
        return _chain_barrier(
            barrier=bridge_barrier,
            on_success=[action for action in phase1 if action is not None]
            + _chain_barrier(
                barrier=control_barrier,
                on_success=[action for action in phase2 if action is not None]
                + _chain_barrier(
                    barrier=decision_barrier,
                    on_success=[action for action in phase3 if action is not None],
                    failure_reason='decision readiness barrier failed',
                ),
                failure_reason='control readiness barrier failed',
            ),
            failure_reason='bridge readiness barrier failed',
        )

    startup_actions = [action for action in phase0 if action is not None]
    startup_actions.append(OpaqueFunction(function=lambda context: _barrier_chain_setup(context)))
    return startup_actions
