from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from robot_bringup.config_resolution import resolve_bringup_config
from robot_contracts.launch_contract import LaunchRuntime, resolve_runtime
from robot_utils.config_loader import ConfigValidationError, load_structured_file
from robot_utils.parameter_schema import validate_launch_profiles
from robot_bringup.matrix_contracts import load_bringup_matrices, profile_feature_matrix, startup_sequence_for_profile, surface_contract_for_profile


@dataclass(frozen=True)
class LaunchProfile:
    name: str
    enable_voice: bool
    enable_vision: bool
    enable_monitor: bool
    enable_teleop: bool
    enable_localization: bool = True
    enable_navigation: bool = False
    enable_hardware_interface: bool = True
    enable_api_server: bool = False
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
    api_server_public_host: str | None = None
    api_server_listen_host: str | None = None
    api_server_port: int = 9100
    api_server_ws_path: str = '/ws'
    api_server_api_prefix: str = '/api/v1'
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
        if self.enable_localization:
            nodes.append('robot_localization')
        if self.enable_navigation:
            nodes.append('robot_navigation')
        if self.enable_hardware_interface:
            nodes.append('robot_hardware_interface')
        if self.enable_api_server:
            nodes.append('robot_api_server')
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
            'localization': self.enable_localization,
            'navigation': self.enable_navigation,
            'hardware_interface': self.enable_hardware_interface,
            'api_server': self.enable_api_server,
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
        """Return the effective startup phases for this profile.

        Args:
            None.

        Returns:
            Ordered startup phase tuple derived from the shared capability matrix.

        Raises:
            ConfigValidationError: If the capability matrix is invalid.
        """
        return startup_sequence_for_profile(self)

    def runtime_supervision_model(self) -> dict[str, object]:
        """Describe how startup readiness and runtime supervision are separated.

        Returns:
            Serializable runtime-supervision policy used by preflight/reporting.

        Raises:
            None.
        """
        matrices = load_bringup_matrices()
        surfaces = surface_contract_for_profile(self)
        web_bridge_surface = surfaces.get('web_bridge', {})
        operator_surface_contract = surfaces.get('frontend', {})
        runtime_supervisor_present = bool(self.enable_monitor)
        lifecycle_manager_present = True
        bond_supervision_present = True
        notes = [
            'startup barrier readiness and runtime supervision are modeled separately so startup success is not mistaken for runtime stability',
            'operator surface readiness requires the web bridge ready topic and the API health contract when API server is enabled',
            'the bringup stack now launches ROS lifecycle wrapper nodes and a ROS lifecycle manager that configures and activates managed components through lifecycle_msgs services',
            'bond supervision is provided by bondpy on the ROS bond topic and lifecycle degradation is surfaced through /robot/lifecycle_manager/status',
            'localization/hardware-interface/api-server remain optional per profile and are reported through the supervision component map when the monitor is enabled',
        ]
        if runtime_supervisor_present:
            notes.append('runtime supervisor publishes /robot/runtime/supervision and embeds authoritative lifecycleManager / bondSupervision / recoveryPlan sections from the ROS lifecycle manager status topic')
        else:
            notes.append('runtime supervision topic is absent when the monitor is disabled; lifecycle manager and bond supervision remain available directly on /robot/lifecycle_manager/status')
        return {
            'startupBarrierEnabled': True,
            'startupBarrierPhases': list(self.startup_sequence()),
            'runtimeHealthSurface': 'connection.runtimeHealthState/runtimeHealthReasons',
            'startupReadinessSurface': (web_bridge_surface.get('ready_topics') or [None])[0] if bool(web_bridge_surface.get('enabled')) else None,
            'supervisionMode': 'startup_barrier_plus_ros_lifecycle_manager' if runtime_supervisor_present else 'startup_barrier_plus_ros_lifecycle_manager_without_monitor',
            'operatorSurfaceContract': operator_surface_contract,
            'surfaceMatrix': surfaces,
            'failureTaxonomy': matrices.failure_taxonomy,
            'runtimeSupervisorPresent': runtime_supervisor_present,
            'lifecycleManagerPresent': lifecycle_manager_present,
            'lifecycleManagerType': 'ros_lifecycle_manager',
            'bondSupervisionPresent': bond_supervision_present,
            'bondSupervisionType': 'bondpy_supervision',
            'recoveryMode': 'ros_lifecycle_manager_safe_shutdown_and_manual_reactivate',
            'runtimeSupervisionTopic': '/robot/runtime/supervision' if runtime_supervisor_present else None,
            'runtimeLifecycleSurface': '/robot/lifecycle_manager/status.lifecycleManager',
            'runtimeBondSurface': '/robot/lifecycle_manager/status.bondSupervision',
            'runtimeRecoveryPlanSurface': '/robot/lifecycle_manager/status.recoveryPlan',
            'lifecycleManagerStatusTopic': '/robot/lifecycle_manager/status',
            'lifecycleManagerReadyTopic': '/robot/lifecycle_manager/ready',
            'notes': notes,
        }

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload['tags'] = list(self.tags)
        payload['enabled_nodes'] = list(self.enabled_nodes())
        payload['feature_matrix'] = self.feature_matrix()
        payload['runtime'] = asdict(self.runtime())
        payload['operational_class'] = self.operational_class()
        payload['startup_sequence'] = list(self.startup_sequence())
        payload['runtime_supervision'] = self.runtime_supervision_model()
        return payload


PROFILE_DEFAULTS: dict[str, LaunchProfile] = {
    'minimal': LaunchProfile('minimal', enable_voice=False, enable_vision=False, enable_monitor=False, enable_teleop=False, enable_localization=True, enable_navigation=False, enable_hardware_interface=True, enable_api_server=False, log_level='warn', use_mock_robot=True, diagnostics_enabled=False, enable_web_bridge=False, preflight_checks_enabled=True),
    'dev': LaunchProfile('dev', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=True, enable_localization=True, enable_navigation=True, enable_hardware_interface=True, enable_api_server=True, log_level='debug', use_mock_robot=True, enable_debug_overlay=True, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
    'demo': LaunchProfile('demo', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=False, enable_localization=True, enable_navigation=True, enable_hardware_interface=True, enable_api_server=True, log_level='info', use_mock_robot=False, enable_debug_overlay=False, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
    'full': LaunchProfile('full', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=True, enable_localization=True, enable_navigation=True, enable_hardware_interface=True, enable_api_server=True, log_level='info', use_mock_robot=False, enable_debug_overlay=True, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
    'hardware': LaunchProfile('hardware', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=True, enable_localization=True, enable_navigation=True, enable_hardware_interface=True, enable_api_server=True, log_level='info', use_mock_robot=False, enable_debug_overlay=False, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
    'mock': LaunchProfile('mock', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=True, enable_localization=True, enable_navigation=True, enable_hardware_interface=True, enable_api_server=True, log_level='debug', use_mock_robot=True, enable_debug_overlay=True, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
    'sim': LaunchProfile('sim', enable_voice=True, enable_vision=True, enable_monitor=True, enable_teleop=True, enable_localization=True, enable_navigation=True, enable_hardware_interface=True, enable_api_server=True, log_level='debug', use_mock_robot=False, enable_debug_overlay=True, diagnostics_enabled=True, enable_web_bridge=True, preflight_checks_enabled=True),
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
            enable_localization=bool(profile.get('enable_localization', base.enable_localization)),
            enable_navigation=bool(profile.get('enable_navigation', base.enable_navigation)),
            enable_hardware_interface=bool(profile.get('enable_hardware_interface', base.enable_hardware_interface)),
            enable_api_server=bool(profile.get('enable_api_server', base.enable_api_server)),
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
            api_server_public_host=(None if profile.get('api_server_public_host') in (None, '') and 'api_server_public_host' in profile else str(profile['api_server_public_host'])) if 'api_server_public_host' in profile else base.api_server_public_host,
            api_server_listen_host=(None if profile.get('api_server_listen_host') in (None, '') and 'api_server_listen_host' in profile else str(profile['api_server_listen_host'])) if 'api_server_listen_host' in profile else base.api_server_listen_host,
            api_server_port=int(profile['api_server_port']) if 'api_server_port' in profile and profile.get('api_server_port') is not None else base.api_server_port,
            api_server_ws_path=str(profile.get('api_server_ws_path', base.api_server_ws_path)),
            api_server_api_prefix=str(profile.get('api_server_api_prefix', base.api_server_api_prefix)),
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
        'enable_localization': 'true' if profile.enable_localization else 'false',
        'enable_navigation': 'true' if profile.enable_navigation else 'false',
        'enable_hardware_interface': 'true' if profile.enable_hardware_interface else 'false',
        'enable_api_server': 'true' if profile.enable_api_server else 'false',
        'use_mock_robot': 'true' if profile.use_mock_robot else 'false',
        'api_server_public_host': profile.api_server_public_host or '',
        'api_server_listen_host': profile.api_server_listen_host or '',
        'api_server_port': str(profile.api_server_port),
        'api_server_ws_path': profile.api_server_ws_path,
        'api_server_api_prefix': profile.api_server_api_prefix,
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
