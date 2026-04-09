from robot_monitor.monitor_node import MonitorNode
from test_monitor_runtime_guards import _FakeNode


_REQUIRED = ['mode_state', 'system_status', 'chassis_state', 'bridge_summary', 'decision_summary', 'control_summary']


def _mark_all_required_ready(node: _FakeNode, *, age_sec: float = 0.0) -> None:
    now_sec = node._now_sec()
    node.snapshot.bridge_ok = True
    for name in _REQUIRED:
        node._component_last_seen[name] = now_sec - float(age_sec)


def test_runtime_supervision_prefers_authoritative_ros_lifecycle_manager_snapshot() -> None:
    node = _FakeNode()
    _mark_all_required_ready(node)
    node._lifecycle_manager_status = {
        'ready': True,
        'lifecycleManager': {
            'present': True,
            'type': 'ros_lifecycle_manager',
            'state': 'active',
            'managedNodes': [{'wrapperName': 'robot_control_lifecycle', 'componentId': 'robot_control', 'actualState': 'active', 'bondState': 'bonded'}],
            'recentTransitions': [{'subject': 'robot_control_lifecycle', 'toState': 'active'}],
        },
        'bondSupervision': {
            'present': True,
            'type': 'bondpy_supervision',
            'state': 'bonded',
            'managedNodes': [{'wrapperName': 'robot_control_lifecycle', 'componentId': 'robot_control', 'bondState': 'bonded'}],
        },
        'recoveryPlan': {'strategy': 'observe_runtime'},
    }

    node._lifecycle_manager_status_at = node._now_sec()

    payload = MonitorNode._runtime_supervision_payload(node)

    assert payload['state'] == 'ready'
    assert payload['lifecycleManager']['type'] == 'ros_lifecycle_manager'
    assert payload['lifecycleManager']['state'] == 'active'
    assert payload['lifecycleManager']['managedNodes'][0]['componentId'] == 'robot_control'
    assert payload['bondSupervision']['type'] == 'bondpy_supervision'
    assert payload['bondSupervision']['state'] == 'bonded'
    assert payload['recoveryPlan']['strategy'] == 'observe_runtime'


def test_runtime_supervision_degrades_when_ros_lifecycle_manager_not_ready() -> None:
    node = _FakeNode()
    _mark_all_required_ready(node)
    node._lifecycle_manager_status = {
        'ready': False,
        'lifecycleManager': {'present': True, 'type': 'ros_lifecycle_manager', 'state': 'inactive'},
        'bondSupervision': {'present': True, 'type': 'bondpy_supervision', 'state': 'broken'},
        'recoveryPlan': {'strategy': 'deactivate_stack_and_manual_reactivate'},
    }

    node._lifecycle_manager_status_at = node._now_sec()

    payload = MonitorNode._runtime_supervision_payload(node)

    assert payload['state'] == 'unavailable'
    assert 'ros_lifecycle_manager_not_active' in payload['reasons']
    assert payload['bondSupervision']['state'] == 'broken'
    assert payload['recoveryPlan']['strategy'] == 'deactivate_stack_and_manual_reactivate'


def test_runtime_supervision_marks_stale_lifecycle_manager_status_unavailable() -> None:
    node = _FakeNode()
    _mark_all_required_ready(node)
    node._lifecycle_manager_status = {
        'ready': True,
        'lifecycleManager': {'present': True, 'type': 'ros_lifecycle_manager', 'state': 'active'},
        'bondSupervision': {'present': True, 'type': 'bondpy_supervision', 'state': 'bonded'},
        'recoveryPlan': {'strategy': 'observe_runtime'},
    }
    node._lifecycle_manager_status_at = node._now_sec() - 10.0

    payload = MonitorNode._runtime_supervision_payload(node)

    assert payload['state'] == 'unavailable'
    assert 'ros_lifecycle_manager_status_stale' in payload['reasons']
    assert payload['lifecycleManager']['present'] is False
    assert payload['bondSupervision']['present'] is False
    assert payload['recoveryPlan']['reason'] == 'ros_lifecycle_manager_status_stale'
