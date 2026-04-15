from robot_monitor.monitor_node import MonitorNode
from test_monitor_runtime_guards import _FakeNode


def test_runtime_supervision_payload_tolerates_missing_voice_ingress_health_attribute() -> None:
    node = _FakeNode()
    if hasattr(node, '_voice_ingress_health'):
        delattr(node, '_voice_ingress_health')
    payload = MonitorNode._runtime_supervision_payload(node)
    assert 'voiceIngressHealth' in payload
    assert payload['voiceIngressHealth'] is None


def test_runtime_supervision_payload_emits_voice_ingress_health_when_present() -> None:
    node = _FakeNode()
    node._voice_ingress_health = {'state': 'ready', 'source': 'asr'}
    payload = MonitorNode._runtime_supervision_payload(node)
    assert payload['voiceIngressHealth'] == {'state': 'ready', 'source': 'asr'}
