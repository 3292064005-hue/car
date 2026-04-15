from __future__ import annotations

import importlib
import sys
import types
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class _FakeLaunchConfiguration:
    def __init__(self, name: str) -> None:
        self.name = name

    def perform(self, context) -> str:
        return str(context.values.get(self.name, ''))


class _FakeSetLaunchConfiguration:
    def __init__(self, name: str, value) -> None:
        self.name = name
        self.value = value


class _FakeLogInfo:
    def __init__(self, *, msg, condition=None) -> None:
        self.msg = msg
        self.condition = condition


class _FakeEmitEvent:
    def __init__(self, *, event) -> None:
        self.event = event


class _FakeShutdown:
    def __init__(self, *, reason: str) -> None:
        self.reason = reason


class _FakeCondition:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class _FakeNode:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs


class _FakeAction:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs


class _FakeContext:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values


_STUBBED_MODULE_NAMES = (
    'launch',
    'launch.actions',
    'launch.conditions',
    'launch.event_handlers',
    'launch.events',
    'launch.substitutions',
    'launch_ros',
    'launch_ros.actions',
    'robot_bringup.config_resolution',
    'robot_bringup.launch_profiles',
    'robot_bringup.launch_common',
    'robot_bridge.runtime_factory',
)


def _install_launch_stubs() -> None:
    launch = types.ModuleType('launch')
    launch_actions = types.ModuleType('launch.actions')
    launch_conditions = types.ModuleType('launch.conditions')
    launch_event_handlers = types.ModuleType('launch.event_handlers')
    launch_events = types.ModuleType('launch.events')
    launch_substitutions = types.ModuleType('launch.substitutions')
    launch_ros = types.ModuleType('launch_ros')
    launch_ros_actions = types.ModuleType('launch_ros.actions')

    launch_actions.DeclareLaunchArgument = _FakeAction
    launch_actions.EmitEvent = _FakeEmitEvent
    launch_actions.ExecuteProcess = _FakeAction
    launch_actions.LogInfo = _FakeLogInfo
    launch_actions.OpaqueFunction = _FakeAction
    launch_actions.RegisterEventHandler = _FakeAction
    launch_actions.SetLaunchConfiguration = _FakeSetLaunchConfiguration

    launch_conditions.IfCondition = _FakeCondition
    launch_conditions.UnlessCondition = _FakeCondition
    launch_event_handlers.OnProcessExit = _FakeAction
    launch_events.Shutdown = _FakeShutdown
    launch_substitutions.LaunchConfiguration = _FakeLaunchConfiguration
    launch_substitutions.PathJoinSubstitution = _FakeAction
    launch_substitutions.PythonExpression = _FakeAction
    launch_ros_actions.Node = _FakeNode

    sys.modules['launch'] = launch
    sys.modules['launch.actions'] = launch_actions
    sys.modules['launch.conditions'] = launch_conditions
    sys.modules['launch.event_handlers'] = launch_event_handlers
    sys.modules['launch.events'] = launch_events
    sys.modules['launch.substitutions'] = launch_substitutions
    sys.modules['launch_ros'] = launch_ros
    sys.modules['launch_ros.actions'] = launch_ros_actions


class _ResolvedConfig:
    def __init__(self) -> None:
        self.config_root = ROOT.parent / 'robot_bringup' / 'config'


def _install_robot_bringup_stubs() -> None:
    config_resolution = types.ModuleType('robot_bringup.config_resolution')
    config_resolution.CONFIG_PATH_INPUT_ENV = 'ROBOT_CONFIG_PATH_INPUT'
    config_resolution.resolve_bringup_config = lambda override=None: _ResolvedConfig()
    launch_profiles = types.ModuleType('robot_bringup.launch_profiles')
    launch_profiles.launch_argument_defaults = lambda profile_name, config_path=None, launch_profiles_path=None: {}
    sys.modules['robot_bringup.config_resolution'] = config_resolution
    sys.modules['robot_bringup.launch_profiles'] = launch_profiles


def _install_bridge_runtime_stubs() -> None:
    runtime_factory = types.ModuleType('robot_bridge.runtime_factory')
    runtime_factory.DEFAULT_BRIDGE_RUNTIME_MODE = 'split_runtime'
    runtime_factory.DEFAULT_BRIDGE_RUNTIME_SPLIT = True
    runtime_factory.LEGACY_MONOLITH_RUNTIME_LABEL = 'legacy_monolith'
    runtime_factory.SPLIT_RUNTIME_LABEL = 'split_runtime'

    def normalize_bridge_runtime_mode(value, *, allow_legacy: bool = True) -> str:
        raw = str(value or '').strip().lower()
        if raw in {'', 'auto', 'default', 'split', 'split_runtime', 'true', '1', 'yes', 'on'}:
            return 'split_runtime'
        if raw in {'legacy', 'legacy_monolith', 'monolith', 'false', '0', 'no', 'off'}:
            if not allow_legacy:
                raise ValueError('legacy monolith runtime is compatibility-only; explicit legacy enablement is required')
            return 'legacy_monolith'
        raise ValueError(f'unsupported bridge runtime mode: {value!r}')

    runtime_factory.normalize_bridge_runtime_mode = normalize_bridge_runtime_mode
    sys.modules['robot_bridge.runtime_factory'] = runtime_factory


@contextmanager
def _isolated_launch_common_module():
    original_modules = {name: sys.modules.get(name) for name in _STUBBED_MODULE_NAMES}
    original_sys_path = list(sys.path)
    try:
        _install_launch_stubs()
        _install_robot_bringup_stubs()
        _install_bridge_runtime_stubs()
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        sys.modules.pop('robot_bringup.launch_common', None)
        yield importlib.import_module('robot_bringup.launch_common')
    finally:
        sys.path[:] = original_sys_path
        for name in _STUBBED_MODULE_NAMES:
            original = original_modules[name]
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def test_bridge_runtime_mode_explicitly_selects_legacy_when_rollback_gate_is_enabled() -> None:
    with _isolated_launch_common_module() as launch_common:
        context = _FakeContext({
            'bridge_runtime_mode': 'legacy_monolith',
            'allow_legacy_bridge_runtime': 'true',
        })
        actions = launch_common._bridge_runtime_setup(context)
        settings = {item.name: item.value for item in actions if isinstance(item, _FakeSetLaunchConfiguration)}
        assert settings['bridge_runtime_mode'] == 'legacy_monolith'
        assert settings['bridge_runtime_split'] == 'false'


def test_bridge_runtime_mode_rejects_legacy_without_explicit_rollback_gate() -> None:
    with _isolated_launch_common_module() as launch_common:
        context = _FakeContext({
            'bridge_runtime_mode': 'legacy_monolith',
            'allow_legacy_bridge_runtime': 'false',
        })
        actions = launch_common._bridge_runtime_setup(context)
        shutdowns = [item for item in actions if isinstance(item, _FakeEmitEvent)]
        assert shutdowns
        assert 'compatibility-only' in shutdowns[0].event.reason


def test_control_barrier_skips_optional_nodes_when_launch_args_disable_them() -> None:
    with _isolated_launch_common_module() as launch_common:
        context = _FakeContext({
            'enable_monitor': 'false',
            'enable_voice': 'true',
            'enable_vision': 'false',
        })
        requirements = launch_common._resolve_control_barrier_requirements(context, include_monitor=True, include_voice=True, include_vision=True)
        assert requirements == {'nodes': ['/robot_control_lifecycle', '/robot_decision_lifecycle', '/robot_navigation_lifecycle', '/robot_voice'], 'services': [], 'actions': []}


def test_control_barrier_adds_vision_service_and_action_requirements_when_enabled() -> None:
    with _isolated_launch_common_module() as launch_common:
        context = _FakeContext({
            'enable_monitor': 'false',
            'enable_voice': 'false',
            'enable_vision': 'true',
        })
        requirements = launch_common._resolve_control_barrier_requirements(context, include_monitor=True, include_voice=True, include_vision=True)
        assert requirements == {
            'nodes': ['/robot_control_lifecycle', '/robot_decision_lifecycle', '/robot_navigation_lifecycle', '/robot_vision'],
            'services': ['/robot/save_snapshot'],
            'actions': ['/robot/actions/save_snapshot'],
        }


def test_operator_surface_http_contract_prefers_public_host_and_requires_operator_ready() -> None:
    with _isolated_launch_common_module() as launch_common:
        context = _FakeContext({
            'enable_api_server': 'true',
            'api_server_public_host': '10.0.0.8',
            'api_server_listen_host': '0.0.0.0',
            'websocket_public_host': '10.0.0.9',
            'bridge_host': '127.0.0.1',
            'api_server_port': '9100',
            'api_server_api_prefix': '/api/v1',
        })
        urls, fields = launch_common._operator_surface_http_contract(context)
        assert urls == ['http://10.0.0.8:9100/api/v1/health']
        assert fields == ['ok', 'operatorSurfaceReady']
