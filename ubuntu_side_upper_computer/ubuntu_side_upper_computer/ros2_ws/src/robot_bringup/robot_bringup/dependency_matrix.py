from __future__ import annotations

"""Launch-surface dependency matrix used by bringup preflight and reports.

This module is the single source of truth for runtime dependencies that vary by
launch profile and operator surface. It intentionally stays independent from the
shell scripts so startup gates, profile reports, and documentation can all speak
about the same dependency contract.
"""

from dataclasses import dataclass
from typing import Literal

from robot_bringup.launch_profiles import LaunchProfile, get_launch_profile

SurfaceName = Literal['backend', 'web_bridge', 'frontend']

BASE_REQUIRED_MODULES = ('json', 'pathlib', 'yaml')
BASE_OPTIONAL_MODULES = ('diagnostic_msgs',)
BASE_REQUIRED_EXECUTABLES = ('python3',)
BACKEND_OPTIONAL_EXECUTABLES = ('node', 'npm')

FRONTEND_REQUIRED_ASSETS = (
    'frontend_package_json_exists',
    'frontend_package_lock_exists',
    'frontend_contract_ts_exists',
    'frontend_contract_json_exists',
    'frontend_node_modules_exists',
)
BACKEND_REQUIRED_ASSETS = ('launch_profiles_exists',)

OPTIONAL_WORKSPACE_ASSETS = (
    'frontend_dist_exists',
    'mock_tool_exists',
    'fault_injector_exists',
    'replay_tool_exists',
    'transport_capture_exists',
    'state_transition_report_script_exists',
    'parameter_schema_report_script_exists',
    'control_summary_report_script_exists',
    'vision_stability_report_script_exists',
    'voice_reject_report_script_exists',
    'command_audit_report_script_exists',
    'archive_metrics_script_exists',
    'fault_dictionary_report_script_exists',
    'command_permission_matrix_report_script_exists',
    'transport_summary_report_script_exists',
)


@dataclass(frozen=True, slots=True)
class DependencyPlan:
    """Profile- and surface-aware dependency plan."""

    profile_name: str
    surface: SurfaceName
    required_python_modules: tuple[str, ...]
    optional_python_modules: tuple[str, ...]
    required_executables: tuple[str, ...]
    optional_executables: tuple[str, ...]
    required_workspace_assets: tuple[str, ...]
    optional_workspace_assets: tuple[str, ...]
    startup_required_modules: tuple[str, ...]
    startup_required_executables: tuple[str, ...]
    startup_required_assets: tuple[str, ...]
    feature_flags: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return {
            'profile': self.profile_name,
            'surface': self.surface,
            'required_python_modules': list(self.required_python_modules),
            'optional_python_modules': list(self.optional_python_modules),
            'required_executables': list(self.required_executables),
            'optional_executables': list(self.optional_executables),
            'required_workspace_assets': list(self.required_workspace_assets),
            'optional_workspace_assets': list(self.optional_workspace_assets),
            'startup_required_modules': list(self.startup_required_modules),
            'startup_required_executables': list(self.startup_required_executables),
            'startup_required_assets': list(self.startup_required_assets),
            'feature_flags': dict(self.feature_flags),
        }



def _normalize_profile(profile_or_name: LaunchProfile | str | None, *, config_path: str | None = None) -> LaunchProfile:
    if isinstance(profile_or_name, LaunchProfile):
        return profile_or_name
    return get_launch_profile(str(profile_or_name or 'full'), config_path=config_path)



def dependency_plan_for(
    profile_or_name: LaunchProfile | str | None = None,
    *,
    surface: SurfaceName = 'backend',
    config_path: str | None = None,
) -> DependencyPlan:
    """Build the dependency contract for one launch profile and surface."""
    profile = _normalize_profile(profile_or_name, config_path=config_path)
    if surface not in {'backend', 'web_bridge', 'frontend'}:
        raise ValueError(f'unsupported preflight surface: {surface}')

    required_modules = list(BASE_REQUIRED_MODULES)
    optional_modules = list(BASE_OPTIONAL_MODULES)
    required_executables = list(BASE_REQUIRED_EXECUTABLES)
    optional_executables: list[str] = []
    required_assets: list[str] = []
    startup_required_modules: list[str] = []
    startup_required_executables: list[str] = []
    startup_required_assets: list[str] = []

    if surface == 'backend':
        required_assets.extend(BACKEND_REQUIRED_ASSETS)
        optional_executables.extend(BACKEND_OPTIONAL_EXECUTABLES)
        startup_required_modules.append('rclpy')
        startup_required_executables.extend(('colcon', 'ros2'))
    elif surface == 'web_bridge':
        required_assets.extend(BACKEND_REQUIRED_ASSETS)
        startup_required_modules.extend(('rclpy', 'websockets'))
        startup_required_executables.extend(('colcon', 'ros2'))
    elif surface == 'frontend':
        required_executables.extend(('node', 'npm'))
        required_assets.extend(FRONTEND_REQUIRED_ASSETS)
        startup_required_executables.extend(('node', 'npm'))
        startup_required_assets.extend(FRONTEND_REQUIRED_ASSETS)

    if profile.enable_vision and surface == 'backend':
        optional_modules.extend(('cv2', 'numpy'))
        startup_required_modules.extend(('cv2', 'numpy'))
    if profile.enable_web_bridge:
        if surface in {'backend', 'web_bridge'}:
            optional_modules.append('websockets')
        if surface == 'backend':
            startup_required_modules.append('websockets')

    return DependencyPlan(
        profile_name=profile.name,
        surface=surface,
        required_python_modules=tuple(dict.fromkeys(required_modules)),
        optional_python_modules=tuple(dict.fromkeys(optional_modules)),
        required_executables=tuple(dict.fromkeys(required_executables)),
        optional_executables=tuple(dict.fromkeys(optional_executables)),
        required_workspace_assets=tuple(dict.fromkeys(required_assets)),
        optional_workspace_assets=OPTIONAL_WORKSPACE_ASSETS,
        startup_required_modules=tuple(dict.fromkeys(startup_required_modules)),
        startup_required_executables=tuple(dict.fromkeys(startup_required_executables)),
        startup_required_assets=tuple(dict.fromkeys(startup_required_assets)),
        feature_flags=profile.feature_matrix(),
    )
