from pathlib import Path
import importlib.util


def _load_resolver():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    spec = importlib.util.spec_from_file_location('resolve_runtime_surface_config', script)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_frontend_uses_api_ws_when_enabled() -> None:
    module = _load_resolver()
    payload = module.build_payload(profile_name='mock', surface='frontend', config_path=None)
    assert payload['runtimeSurface']['apiWebsocketUrl'].startswith('ws://')
    assert payload['frontendEnv']['VITE_ROBOT_WS_URL'] == payload['runtimeSurface']['apiWebsocketUrl']
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_API_BASE_URL'].startswith('http://')
    assert payload['runtimeSurface']['deploymentTier'] == 'host_harness'
    assert payload['runtimeSurface']['operatorSessionBootstrapMode'] == 'local_auto'


def test_backend_keeps_bridge_ws_as_runtime_default() -> None:
    module = _load_resolver()
    payload = module.build_payload(profile_name='mock', surface='backend', config_path=None)
    assert payload['runtimeSurface']['websocketUrl'] == payload['runtimeSurface']['bridgeWebsocketUrl']
    assert payload['runtimeSurface']['operatorSessionBootstrapMode'] == 'disabled'
