from robot_monitor.monitor_node import MonitorNode
from test_monitor_runtime_guards import _FakeNode


def test_runtime_supervision_exposes_ros_lifecycle_manager_and_bond_supervision() -> None:
    node = _FakeNode()
    now_sec = node._now_sec()
    node.snapshot.bridge_ok = True
    for name in ['mode_state', 'system_status', 'chassis_state', 'bridge_summary', 'decision_summary', 'control_summary']:
        node._component_last_seen[name] = now_sec
    node._lifecycle_manager_status = {
        'ready': True,
        'lifecycleManager': {'present': True, 'type': 'ros_lifecycle_manager', 'state': 'active'},
        'bondSupervision': {'present': True, 'type': 'bondpy_supervision', 'state': 'bonded'},
        'recoveryPlan': {'strategy': 'observe_runtime'},
    }
    node._lifecycle_manager_status_at = node._now_sec()

    payload = MonitorNode._runtime_supervision_payload(node)
    assert payload['state'] == 'ready'
    assert payload['lifecycleManager']['present'] is True
    assert payload['lifecycleManager']['type'] == 'ros_lifecycle_manager'
    assert payload['lifecycleManager']['state'] == 'active'
    assert payload['bondSupervision']['present'] is True
    assert payload['bondSupervision']['type'] == 'bondpy_supervision'
    assert payload['bondSupervision']['state'] == 'bonded'
    assert payload['recoveryPlan']['strategy'] == 'observe_runtime'
