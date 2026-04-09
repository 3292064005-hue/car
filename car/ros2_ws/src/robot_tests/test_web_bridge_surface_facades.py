from types import SimpleNamespace

from robot_web_bridge.components.command_surface import CommandSurface
from robot_web_bridge.components.projection_surface import ProjectionSurface


class _Param:
    def __init__(self, value):
        self.value = value


class _Client:
    def wait_for_service(self, timeout_sec: float) -> bool:
        return True


class _ActionClient:
    def wait_for_server(self, timeout_sec: float) -> bool:
        return True


class _Logger:
    def info(self, *_args, **_kwargs):
        return None

    warn = error = debug = info


class _Node:
    def __init__(self) -> None:
        self.state_store = SimpleNamespace(record_trace_id=lambda *_args, **_kwargs: None)
        self.state = SimpleNamespace()
        self.mode_client = _Client()
        self.reset_client = _Client()
        self.snapshot_client = _Client()
        self.get_logger = lambda: _Logger()
        self.now_iso = lambda: '2026-04-08T00:00:00Z'
        self.send_ack = lambda *_args, **_kwargs: None
        self.on_dispatcher_observation = lambda *_args, **_kwargs: None
        self._build_snapshot_envelope = lambda: {'type': 'snapshot', 'payload': {}}
        self._params = {
            'command_future_timeout_sec': 10.0,
            'ingress_queue_max': 16,
            'dispatch_reserved_high_priority_slots': 2,
            'teleop_latest_only': True,
        }

    def get_parameter(self, name: str):
        return _Param(self._params[name])


def test_command_surface_builds_router_dispatcher_and_runtime_coordinator(monkeypatch) -> None:
    node = _Node()

    class _Router:
        def __init__(self, *_args, **_kwargs):
            self.patrol_action_client = _ActionClient()
            self.track_action_client = _ActionClient()
            self.snapshot_action_client = _ActionClient()

    monkeypatch.setattr('robot_web_bridge.components.command_surface.CommandRouter', _Router)
    surface = CommandSurface.build(node=node)
    assert surface.router is not None
    assert surface.dispatcher is not None
    assert surface.runtime_params is not None
    assert surface.readiness is not None


def test_projection_surface_builds_projector_and_snapshot_cache() -> None:
    node = _Node()
    surface = ProjectionSurface.build(node=node)
    assert surface.projector is not None
    assert surface.snapshot_cache.refresh()['type'] == 'snapshot'
