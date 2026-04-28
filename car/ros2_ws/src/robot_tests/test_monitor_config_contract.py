from pathlib import Path


def test_monitor_yaml_declares_voice_ingress_health_topic() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / 'ros2_ws' / 'src' / 'robot_bringup' / 'config' / 'monitor.yaml').read_text(encoding='utf-8')
    assert 'voice_ingress_health_topic:' in source
    assert 'system_replay_auto_export:' in source


def test_runtime_surface_contract_marks_frontend_session_pre_bootstrap() -> None:
    root = Path(__file__).resolve().parents[3]
    import importlib.util
    script = root / 'scripts' / 'resolve_runtime_surface_config.py'
    spec = importlib.util.spec_from_file_location('resolve_runtime_surface_config_monitor_contract', script)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    payload = module.build_payload(profile_name='mock', surface='frontend', config_path=None)
    assert payload['runtimeSurface']['frontendSessionContractStage'] == 'pre_bootstrap'
    assert payload['runtimeSurface']['frontendSessionEffectiveSource'] == 'runtime_bootstrap'
