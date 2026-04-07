from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_resolve_runtime_surface_config_emits_frontend_env(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    output = tmp_path / 'resolved.json'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['surface'] == 'frontend'
    assert payload['frontendEnv']['VITE_ROBOT_WS_URL'] == 'ws://127.0.0.1:9001/ws'
    assert payload['runtimeSurface']['websocketListenHost'] == '0.0.0.0'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_PROFILE'] == 'mock'
    assert payload['runtimeSurface']['contractArtifactPath'] == str(output.with_suffix('.json'))
    assert json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))['surface'] == 'frontend'


def test_resolve_runtime_surface_config_honors_profile_websocket_overrides(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'resolve_runtime_surface_config.py'
    config_root = tmp_path / 'cfg'
    config_root.mkdir()
    (config_root / 'launch_profiles.yaml').write_text(
        '''profiles:
  mock:
    enable_voice: true
    enable_vision: true
    enable_monitor: true
    enable_teleop: true
    use_mock_robot: true
    enable_web_bridge: true
    bridge_host: 127.0.0.1
    bridge_port: 9000
    mjpeg_url: http://127.0.0.1:8080/stream
    websocket_public_host: 10.0.0.8
    websocket_listen_host: 0.0.0.0
    websocket_port: 9102
    websocket_path: /robot/ws
''',
        encoding='utf-8',
    )
    output = tmp_path / 'resolved.json'
    subprocess.run(
        [sys.executable, str(script), '--profile', 'mock', '--surface', 'frontend', '--config-path', str(config_root), '--output', str(output)],
        cwd=str(repo_root),
        check=True,
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert payload['runtimeSurface']['websocketUrl'] == 'ws://10.0.0.8:9102/robot/ws'
    assert payload['runtimeEnv']['ROBOT_EFFECTIVE_WS_LISTEN_HOST'] == '0.0.0.0'
    assert payload['frontendEnv']['VITE_ROBOT_WS_URL'] == 'ws://10.0.0.8:9102/robot/ws'
