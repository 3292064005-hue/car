from robot_bringup.launch_profiles import get_launch_profile


def test_hardware_profile_startup_sequence_matches_effective_enabled_surfaces() -> None:
    profile = get_launch_profile('hardware')
    assert profile.startup_sequence() == ('contracts', 'bridge', 'control', 'monitor', 'platform', 'vision_voice', 'navigation', 'lifecycle', 'decision', 'frontend')


def test_minimal_profile_startup_sequence_prunes_disabled_capability_groups() -> None:
    profile = get_launch_profile('minimal')
    assert profile.startup_sequence() == ('contracts', 'bridge', 'control', 'platform', 'lifecycle', 'decision')


def test_launch_profile_runtime_supervision_model_separates_startup_and_runtime_health() -> None:
    profile = get_launch_profile('mock')
    supervision = profile.runtime_supervision_model()
    assert supervision['startupBarrierEnabled'] is True
    assert supervision['startupReadinessSurface'] == '/robot/web_bridge/ready'
    assert supervision['runtimeHealthSurface'] == 'connection.runtimeHealthState/runtimeHealthReasons'
    assert supervision['supervisionMode'] == 'startup_barrier_plus_ros_lifecycle_manager'
    assert supervision['operatorSurfaceContract']['require_operator_ready'] is True
    assert supervision['operatorSurfaceContract']['ready_http_urls'] == ['http://127.0.0.1:9100/api/v1/health']
    assert supervision['runtimeSupervisorPresent'] is True
    assert supervision['lifecycleManagerPresent'] is True
    assert supervision['lifecycleManagerType'] == 'ros_lifecycle_manager'
    assert supervision['bondSupervisionPresent'] is True
    assert supervision['bondSupervisionType'] == 'bondpy_supervision'
    assert supervision['runtimeSupervisionTopic'] == '/robot/runtime/supervision'
    assert supervision['runtimeOrchestrationTopic'] == '/robot/runtime/orchestration'
    assert supervision['runtimeOrchestrationReadyTopic'] == '/robot/runtime/orchestration/ready'
    assert supervision['runtimeLifecycleSurface'] == '/robot/lifecycle_manager/status.lifecycleManager'
    assert supervision['runtimeBondSurface'] == '/robot/lifecycle_manager/status.bondSupervision'
    assert supervision['runtimeRecoveryPlanSurface'] == '/robot/lifecycle_manager/status.recoveryPlan'


def test_minimal_profile_runtime_supervision_model_is_honest_about_disabled_monitor() -> None:
    profile = get_launch_profile('minimal')
    supervision = profile.runtime_supervision_model()
    assert supervision['runtimeSupervisorPresent'] is False
    assert supervision['lifecycleManagerPresent'] is True
    assert supervision['bondSupervisionPresent'] is True
    assert supervision['supervisionMode'] == 'startup_barrier_plus_ros_lifecycle_manager_without_monitor'
    assert supervision['runtimeSupervisionTopic'] is None
    assert supervision['runtimeOrchestrationTopic'] is None
    assert supervision['runtimeOrchestrationReadyTopic'] is None
    assert supervision['recoveryMode'] == 'ros_lifecycle_manager_safe_shutdown_and_manual_reactivate'
