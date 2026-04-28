from __future__ import annotations

from robot_bringup.runtime_orchestration_manager import RuntimeOrchestrationSnapshot, evaluate_runtime_orchestration


def test_runtime_orchestration_manager_reports_startup_until_required_fields_arrive() -> None:
    status = evaluate_runtime_orchestration(
        RuntimeOrchestrationSnapshot(
            runtime_supervision={
                'state': 'booting',
                'startupBarrierReady': False,
                'readiness': 'booting',
                'reasons': ['awaiting_samples'],
            },
            lifecycle_status={'ready': False},
            web_bridge_ready=False,
        )
    )
    assert status.state == 'startup'
    assert status.ready is False


def test_runtime_orchestration_manager_reports_paused_when_safe_stop_is_recoverable() -> None:
    status = evaluate_runtime_orchestration(
        RuntimeOrchestrationSnapshot(
            runtime_supervision={
                'state': 'ready',
                'startupBarrierReady': True,
                'readiness': 'ready',
                'reasons': ['all_core_components_fresh'],
                'recoveryMode': 'observe_and_recover',
                'recoveryPlan': {'strategy': 'observe_runtime', 'reason': 'n/a', 'targetNodes': []},
                'lifecycleManager': {'present': True, 'type': 'ros_lifecycle_manager', 'state': 'active', 'managedNodes': [], 'recentTransitions': []},
                'bondSupervision': {'present': True, 'type': 'bondpy_supervision', 'state': 'bonded', 'managedNodes': []},
            },
            lifecycle_status={'ready': True},
            decision_summary={'mode': 'SAFE_STOP', 'safe_stop_recoverable': True, 'safe_stop_blocked_reason': ''},
            web_bridge_ready=True,
        )
    )
    assert status.state == 'paused'
    assert status.ready is True


def test_runtime_orchestration_manager_reports_shutdown_when_requested() -> None:
    status = evaluate_runtime_orchestration(
        RuntimeOrchestrationSnapshot(
            runtime_supervision={'state': 'ready', 'startupBarrierReady': True, 'readiness': 'ready', 'reasons': ['all_core_components_fresh']},
            shutdown_requested=True,
        )
    )
    assert status.state == 'shutting_down'
    assert status.reason == 'bringup_shutdown_requested'
