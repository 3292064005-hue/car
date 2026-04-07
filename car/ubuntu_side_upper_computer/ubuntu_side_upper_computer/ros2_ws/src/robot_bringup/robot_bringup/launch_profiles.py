from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from robot_bringup.config_resolution import resolve_bringup_config
from robot_contracts.launch_contract import LaunchRuntime, resolve_runtime
from robot_utils.config_loader import ConfigValidationError, load_structured_file
from robot_utils.parameter_schema import validate_launch_profiles


@dataclass(frozen=True)
class LaunchProfile:
    name: str
    enable_voice: bool
    enable_vision: bool
    enable_monitor: bool
    enable_teleop: bool
    log_level: str = 'info'
    use_mock_robot: bool = False
    enable_debug_overlay: bool = False
    diagnostics_enabled: bool = True
    enable_web_bridge: bool = True
    preflight_checks_enabled: bool = True
    bridge_host: str | None = None
    bridge_port: int | None = None
    mjpeg_url: str | None = None
    websocket_public_host: str | None = None
    websocket_listen_host: str | None = None
    websocket_port: int = 9001
    websocket_path: str = '/ws'
    description: str = ''
    tags: tuple[str, ...] = ()

    def enabled_nodes(self) -> tuple[str, ...]:
        nodes = ['robot_decision', 'robot_control', 'robot_bridge']
        if self.enable_voice:
            nodes.append('robot_voice')
        if self.enable_vision:
            nodes.append('robot_vision')
        if self.enable_monitor:
            nodes.append('robot_monitor')
        if self.enable_teleop:
            nodes.append('robot_teleop')
        if self.enable_web_bridge:
            nodes.append('robot_web_bridge')
        return tuple(nodes)

    def feature_matrix(self) -> dict[str, bool]:
        return {
            'voice': self.enable_voice,
            'vision': self.enable_vision,
            'monitor': self.enable_monitor,
            'teleop': self.enable_teleop,
            'mock_robot': self.use_mock_robot,
            'debug_overlay': self.enable_debug_overlay,
            'diagnostics': self.diagnostics_enabled,
            'web_bridge': self.enable_web_bridge,
            'preflight_checks': self.preflight_checks_enabled,
        }

    def runtime(self) -> LaunchRuntime:
        return resolve_runtime(
            use_mock_robot=self.use_mock_robot,
            bridge_host=self.bridge_host,
            bridge_port=self.bridge_port,
            mjpeg_url=self.mjpeg_url,
            web_bridge_enabled=self.enable_web_bridge,
            allow_default_stream=self.enable_vision or self.enable_web_bridge or self.mjpeg_url is not None,
        )

    def operational_class(self) -> str:
        if self.use_mock_robot:
            return 'mock'
        if self.name in {'demo', 'hardware'}:
            return 'hardware_stable'
        return 'hardware_debug'

    def startup_sequence(self) -> tuple[str, ...]:
        return ('contracts', 'bridge', 'control', 'monitor', 'vision_voice', 'decision', 'frontend')

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload['tags'] = list(self.tags)
        payload['enabled_nodes'] = list(self.enabled_nodes())
        payload['feature_matrix'] = self.feature_matrix()
        payload['runtime'] = asdict(self.runtime())
        payload['operational_class'] = self.operational_class()
        payload['startup_sequence'] = list(self.startup_sequence())
        return payload


PROFILE_DEFAULTS: dict[str, LaunchProfile] = {
    'minimal': LaunchProfile('minimal', enable_voice=False, enable_vision=False, enable_monitor=False, enable_teleop=False, log_level='warn', use_mock_robot=True, diagnostics_enabled=False, enable_web_bridge=False, preflight_checks_enabled=True),
    'dev': LaunchProfile('dev', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=True, log_level='debug', use_mock_robot=True, enable_debug_overlay=True, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
    'demo': LaunchProfile('demo', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=False, log_level='info', use_mock_robot=False, enable_debug_overlay=False, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
    'full': LaunchProfile('full', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=True, log_level='info', use_mock_robot=False, enable_debug_overlay=True, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
    'hardware': LaunchProfile('hardware', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=True, log_level='info', use_mock_robot=False, enable_debug_overlay=False, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
    'mock': LaunchProfile('mock', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=True, log_level='debug', use_mock_robot=True, enable_debug_overlay=True, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
}


@lru_cache(maxsize=8)
def _load_profile_overrides(launch_profiles_path: str) -> dict[str, LaunchProfile]:
    payload = load_structured_file(launch_profiles_path, {})
    if not payload:
        return {}
    try:
        validated = validate_launch_profiles(payload)
    except ConfigValidationError:
        return {}
    profiles: dict[str, LaunchProfile] = {}
    for name, profile in validated.items():
        base = PROFILE_DEFAULTS.get(name, LaunchProfile(name, True, True, True, True))
        profiles[name] = LaunchProfile(
            name=name,
            enable_voice=bool(profile.get('enable_voice', base.enable_voice)),
            enable_vision=bool(profile.get('enable_vision', base.enable_vision)),
            enable_monitor=bool(profile.get('enable_monitor', base.enable_monitor)),
            enable_teleop=bool(profile.get('enable_teleop', base.enable_teleop)),
            log_level=str(profile.get('log_level', base.log_level)),
            use_mock_robot=bool(profile.get('use_mock_robot', base.use_mock_robot)),
            enable_debug_overlay=bool(profile.get('enable_debug_overlay', base.enable_debug_overlay)),
            diagnostics_enabled=bool(profile.get('diagnostics_enabled', base.diagnostics_enabled)),
            enable_web_bridge=bool(profile.get('enable_web_bridge', base.enable_web_bridge)),
            preflight_checks_enabled=bool(profile.get('preflight_checks_enabled', base.preflight_checks_enabled)),
            bridge_host=(None if profile.get('bridge_host') in (None, '') and 'bridge_host' in profile else str(profile['bridge_host'])) if 'bridge_host' in profile else base.bridge_host,
            bridge_port=int(profile['bridge_port']) if 'bridge_port' in profile and profile.get('bridge_port') is not None else base.bridge_port,
            mjpeg_url=(
                None
                if ('stream_url' not in profile and 'mjpeg_url' not in profile and base.mjpeg_url is None)
                else (
                    None
                    if ((profile.get('stream_url') if 'stream_url' in profile else profile.get('mjpeg_url')) in (None, '')) and ('stream_url' in profile or 'mjpeg_url' in profile)
                    else str(profile.get('stream_url') or profile.get('mjpeg_url') or base.mjpeg_url)
                )
            ),
            websocket_public_host=(None if profile.get('websocket_public_host') in (None, '') and 'websocket_public_host' in profile else str(profile['websocket_public_host'])) if 'websocket_public_host' in profile else base.websocket_public_host,
            websocket_listen_host=(None if profile.get('websocket_listen_host') in (None, '') and 'websocket_listen_host' in profile else str(profile['websocket_listen_host'])) if 'websocket_listen_host' in profile else base.websocket_listen_host,
            websocket_port=int(profile['websocket_port']) if 'websocket_port' in profile and profile.get('websocket_port') is not None else base.websocket_port,
            websocket_path=str(profile.get('websocket_path', base.websocket_path)),
            description=str(profile.get('description', base.description)),
            tags=tuple(str(item) for item in profile.get('tags', list(base.tags))),
        )
    return profiles



def _resolved_profiles_path(config_path: str | None = None) -> str:
    return str(resolve_bringup_config(config_path).launch_profiles_path)



def _profile_overrides(*, config_path: str | None = None, launch_profiles_path: str | None = None) -> dict[str, LaunchProfile]:
    if launch_profiles_path is not None:
        return _load_profile_overrides(str(Path(launch_profiles_path)))
    return _load_profile_overrides(_resolved_profiles_path(config_path))



def get_launch_profile(name: str, *, config_path: str | None = None, launch_profiles_path: str | None = None) -> LaunchProfile:
    """Return one effective launch profile.

    Args:
        name: Launch profile name.
        config_path: Optional config directory or ``launch_profiles.yaml`` path.

    Returns:
        Effective launch profile, falling back to ``full`` when the requested
        profile is unknown.

    Raises:
        None.
    """
    overrides = _profile_overrides(config_path=config_path, launch_profiles_path=launch_profiles_path)
    if name in overrides:
        return overrides[name]
    return PROFILE_DEFAULTS.get(name, PROFILE_DEFAULTS['full'])



def supported_profiles(*, config_path: str | None = None, launch_profiles_path: str | None = None) -> tuple[str, ...]:
    """Return all known launch profile names for the active config source."""
    names = set(PROFILE_DEFAULTS.keys()) | set(_profile_overrides(config_path=config_path, launch_profiles_path=launch_profiles_path).keys())
    return tuple(sorted(names))



def launch_profile_resolution(config_path: str | None = None, launch_profiles_path: str | None = None) -> dict[str, Any]:
    """Return a serializable description of the active launch-profile source."""
    resolved = resolve_bringup_config(config_path if launch_profiles_path is None else launch_profiles_path)
    return {
        'config_root': str(resolved.config_root),
        'launch_profiles_path': str(Path(launch_profiles_path)) if launch_profiles_path is not None else str(resolved.launch_profiles_path),
        'raw_input': resolved.raw_input,
        'source': resolved.source,
    }



def launch_argument_defaults(name: str, *, config_path: str | None = None, launch_profiles_path: str | None = None) -> dict[str, str]:
    """Resolve profile-derived launch argument defaults.

    Args:
        name: Launch profile name.
        config_path: Optional config root or launch-profile path override.
        launch_profiles_path: Optional explicit ``launch_profiles.yaml`` path.

    Returns:
        Dictionary mapping launch argument names to their resolved default values.

    Raises:
        None.
    """
    profile = get_launch_profile(name, config_path=config_path, launch_profiles_path=launch_profiles_path)
    runtime = profile.runtime()
    return {
        'log_level': profile.log_level,
        'enable_voice': 'true' if profile.enable_voice else 'false',
        'enable_vision': 'true' if profile.enable_vision else 'false',
        'enable_monitor': 'true' if profile.enable_monitor else 'false',
        'enable_teleop': 'true' if profile.enable_teleop else 'false',
        'use_mock_robot': 'true' if profile.use_mock_robot else 'false',
        'enable_debug_overlay': 'true' if profile.enable_debug_overlay else 'false',
        'diagnostics_enabled': 'true' if profile.diagnostics_enabled else 'false',
        'enable_web_bridge': 'true' if profile.enable_web_bridge else 'false',
        'bridge_host': runtime.bridge.host,
        'bridge_port': str(runtime.bridge.port),
        'mjpeg_url': runtime.bridge.mjpeg_url or '',
        'websocket_public_host': profile.websocket_public_host or ('127.0.0.1' if profile.use_mock_robot else runtime.bridge.host),
        'websocket_listen_host': profile.websocket_listen_host or '0.0.0.0',
        'websocket_port': str(profile.websocket_port),
        'websocket_path': profile.websocket_path,
    }



def reset_launch_profile_cache() -> None:
    _load_profile_overrides.cache_clear()
