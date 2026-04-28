from robot_bringup.preflight import build_preflight_report


def test_preflight_report_for_dev_profile_is_not_blocked() -> None:
    report = build_preflight_report('dev')
    assert report['profile'] == 'dev'
    assert report['blocked'] is False
    assert any(item['name'] == 'bridge_endpoint' for item in report['checks'])
    assert 'event_log_path' in report['runtime_paths']


def test_preflight_startup_gate_records_startup_checks(monkeypatch) -> None:
    monkeypatch.setattr('robot_bringup.preflight.startup_gate_entries', lambda _root, profile_name='full', surface='backend', config_path=None: [{
        'name': 'startup_executable:ros2',
        'ok': True,
        'detail': '/usr/bin/ros2',
        'blocking': False,
        'severity': 'info',
        'phase': 'startup_gate',
    }])
    report = build_preflight_report('dev', startup_gate=True)
    assert report['startup_gate_enabled'] is True
    assert any(item['phase'] == 'startup_gate' for item in report['checks'])


def test_preflight_report_exposes_dependency_plan_and_hardware_boundary() -> None:
    report = build_preflight_report('hardware', surface='backend')
    assert report['environment']['dependency_plan']['surface'] == 'backend'
    assert report['hardware_boundary']['launch_profile_requires_real_robot'] is True



def test_web_bridge_surface_does_not_require_backend_vision_python_modules() -> None:
    from robot_bringup.dependency_matrix import dependency_plan_for

    plan = dependency_plan_for('mock', surface='web_bridge')

    assert 'cv2' not in plan.startup_required_modules
    assert 'numpy' not in plan.startup_required_modules
    assert 'websockets' in plan.startup_required_modules


def test_preflight_report_requires_ros2_control_standardization_artifacts_for_real_robot_lane() -> None:
    report = build_preflight_report('hardware', surface='backend')
    names = {item['name']: item for item in report['checks']}
    assert names['ros2_control_artifact:controllersConfig']['ok'] is True
    assert names['ros2_control_artifact:urdfOverlay']['ok'] is True
