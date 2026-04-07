from __future__ import annotations

"""Helpers for resolving bringup configuration roots and files.

The backend historically accepted ``--config-path`` only for launch-profile
preflight overrides. Runtime launch files still consumed the packaged
``share/robot_bringup/config`` tree, which created a silent mismatch between the
operator-selected configuration and the configuration actually used by nodes.

This module centralizes resolution so preflight, launch generation, validation
scripts, and report scripts all resolve the same effective configuration root.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

CONFIG_PATH_INPUT_ENV = 'ROBOT_CONFIG_PATH_INPUT'
CONFIG_ROOT_ENV = 'ROBOT_CONFIG_ROOT'
LAUNCH_PROFILES_PATH_ENV = 'ROBOT_LAUNCH_PROFILES_PATH'

_CONFIG_FILE_SUFFIXES = {'.yaml', '.yml', '.json'}


@dataclass(frozen=True, slots=True)
class ResolvedBringupConfig:
    """Resolved bringup configuration paths.

    Args:
        config_root: Effective configuration directory consumed by runtime nodes.
        launch_profiles_path: Effective launch-profile file.
        raw_input: Raw external override string, if any.
        source: Human-readable source label describing how resolution happened.

    Returns:
        Immutable resolution result.

    Raises:
        None.
    """

    config_root: Path
    launch_profiles_path: Path
    raw_input: str | None
    source: str



def _normalize_candidate(value: str | os.PathLike[str] | None) -> str | None:
    raw = str(value).strip() if value is not None else ''
    return raw or None



def _package_root() -> Path:
    return Path(__file__).resolve().parents[1]



def default_config_root() -> Path:
    """Return the repository/package default configuration root.

    Args:
        None.

    Returns:
        Absolute path to the default bringup configuration directory.

    Raises:
        None.
    """
    return (_package_root() / 'config').resolve()



def default_launch_profiles_path() -> Path:
    """Return the default launch-profile file path.

    Args:
        None.

    Returns:
        Absolute path to ``launch_profiles.yaml`` under the default config root.

    Raises:
        None.
    """
    return default_config_root() / 'launch_profiles.yaml'



def resolve_bringup_config(
    config_path: str | os.PathLike[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> ResolvedBringupConfig:
    """Resolve the effective bringup config directory and launch-profile file.

    Resolution precedence is:

    1. Explicit ``config_path`` argument.
    2. ``ROBOT_CONFIG_ROOT`` / ``ROBOT_LAUNCH_PROFILES_PATH`` environment.
    3. ``ROBOT_CONFIG_PATH_INPUT`` environment.
    4. Packaged default config directory.

    ``config_path`` may point to either a directory containing the bringup YAML
    files or directly to ``launch_profiles.yaml``. Directory overrides affect the
    entire runtime configuration tree; file overrides still derive the runtime
    root from the file's parent directory.

    Args:
        config_path: Optional operator-provided config directory or profile file.
        env: Optional environment mapping. Defaults to ``os.environ``.

    Returns:
        ``ResolvedBringupConfig`` containing the effective paths.

    Raises:
        None. Existence checks are performed by callers so the resolver can be
        used safely during launch-description generation.
    """
    environ = dict(os.environ if env is None else env)
    explicit_root = _normalize_candidate(environ.get(CONFIG_ROOT_ENV))
    explicit_profiles = _normalize_candidate(environ.get(LAUNCH_PROFILES_PATH_ENV))
    raw_input = _normalize_candidate(config_path)
    source = 'default'

    if raw_input is None and explicit_root is not None:
        raw_input = explicit_root
        source = f'env:{CONFIG_ROOT_ENV}'
    elif raw_input is None and explicit_profiles is not None:
        raw_input = explicit_profiles
        source = f'env:{LAUNCH_PROFILES_PATH_ENV}'
    elif raw_input is None:
        raw_input = _normalize_candidate(environ.get(CONFIG_PATH_INPUT_ENV))
        if raw_input is not None:
            source = f'env:{CONFIG_PATH_INPUT_ENV}'
    else:
        source = 'argument'

    if raw_input is None:
        config_root = default_config_root()
        launch_profiles_path = default_launch_profiles_path()
        return ResolvedBringupConfig(
            config_root=config_root,
            launch_profiles_path=launch_profiles_path,
            raw_input=None,
            source=source,
        )

    candidate = Path(raw_input).expanduser().resolve(strict=False)
    if explicit_profiles is not None and source == f'env:{LAUNCH_PROFILES_PATH_ENV}':
        launch_profiles_path = candidate
        config_root = candidate.parent
    elif candidate.suffix.lower() in _CONFIG_FILE_SUFFIXES and candidate.name == 'launch_profiles.yaml':
        launch_profiles_path = candidate
        config_root = candidate.parent
        source = f'{source}:launch_profiles_file'
    elif candidate.suffix.lower() in _CONFIG_FILE_SUFFIXES and not candidate.is_dir():
        config_root = candidate.parent
        launch_profiles_path = config_root / 'launch_profiles.yaml'
        source = f'{source}:config_file_parent'
    else:
        config_root = candidate
        launch_profiles_path = config_root / 'launch_profiles.yaml'
        source = f'{source}:config_root'
    return ResolvedBringupConfig(
        config_root=config_root,
        launch_profiles_path=launch_profiles_path,
        raw_input=raw_input,
        source=source,
    )



def resolve_config_root(config_path: str | os.PathLike[str] | None = None, *, env: Mapping[str, str] | None = None) -> Path:
    """Return only the effective bringup config root.

    Args:
        config_path: Optional config override.
        env: Optional environment mapping.

    Returns:
        Absolute config root path.

    Raises:
        None.
    """
    return resolve_bringup_config(config_path, env=env).config_root



def resolve_launch_profiles_path(config_path: str | os.PathLike[str] | None = None, *, env: Mapping[str, str] | None = None) -> Path:
    """Return the effective launch-profile file path.

    Args:
        config_path: Optional config override.
        env: Optional environment mapping.

    Returns:
        Absolute path to the launch-profile file.

    Raises:
        None.
    """
    return resolve_bringup_config(config_path, env=env).launch_profiles_path



def resolve_config_file(name: str, config_path: str | os.PathLike[str] | None = None, *, env: Mapping[str, str] | None = None) -> Path:
    """Resolve one named bringup config file under the effective root.

    Args:
        name: Bringup YAML filename.
        config_path: Optional config override.
        env: Optional environment mapping.

    Returns:
        Absolute path to the requested file.

    Raises:
        ValueError: If ``name`` is empty.
    """
    normalized = str(name).strip()
    if not normalized:
        raise ValueError('config file name must be non-empty')
    return resolve_config_root(config_path, env=env) / normalized
