from pathlib import Path

from robot_utils.callback_groups import build_callback_groups
from robot_utils.config_loader import StructuredConfigLoadError
from robot_utils.error_policy import ERROR_STARTUP_FAILED, classify_exception

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def test_error_policy_classifies_config_load_as_startup_failed() -> None:
    outcome = classify_exception('decision.patrol_config', StructuredConfigLoadError('bad config'))
    assert outcome.disposition == ERROR_STARTUP_FAILED
    assert outcome.code == 'CONFIG_LOAD_FAILED'
    assert outcome.fault_level is not None


def test_callback_group_partitioning_is_wired_into_core_nodes() -> None:
    targets = {
        'robot_decision/robot_decision/decision_node.py': ['build_callback_groups()', 'call_with_callback_group(self.create_subscription', 'callback_group=self.callback_groups.control'],
        'robot_web_bridge/robot_web_bridge/web_bridge_node.py': ['build_callback_groups()', 'call_with_callback_group(self.create_subscription', 'callback_group=self.callback_groups.background'],
        'robot_monitor/robot_monitor/monitor_node.py': ['build_callback_groups()', 'call_with_callback_group(self.create_timer'],
        'robot_voice/robot_voice/voice_node.py': ['build_callback_groups()', 'MultiThreadedExecutor'],
        'robot_bridge/robot_bridge/bridge_node.py': ['build_callback_groups()', 'MultiThreadedExecutor'],
        'robot_bridge/robot_bridge/bridge_transport_node.py': ['build_callback_groups()', 'call_with_callback_group(self.create_subscription', 'MultiThreadedExecutor'],
        'robot_bridge/robot_bridge/bridge_protocol_node.py': ['build_callback_groups()', 'call_with_callback_group(self.create_timer', 'MultiThreadedExecutor'],
        'robot_bridge/robot_bridge/bridge_projection_node.py': ['build_callback_groups()', 'call_with_callback_group(self.create_subscription', 'publish_policy_outcome', 'MultiThreadedExecutor'],
        'robot_bridge/robot_bridge/bridge_health_node.py': ['build_callback_groups()', 'call_with_callback_group(self.create_subscription', 'publish_policy_outcome', 'MultiThreadedExecutor'],
    }
    for rel_path, markers in targets.items():
        content = _read(rel_path)
        for marker in markers:
            assert marker in content, f'{rel_path} missing callback/executor partition marker: {marker}'


def test_callback_groups_degrade_safely_in_lightweight_env() -> None:
    groups = build_callback_groups()
    assert hasattr(groups, 'control')
    assert hasattr(groups, 'telemetry')
    assert hasattr(groups, 'io')
    assert hasattr(groups, 'background')
