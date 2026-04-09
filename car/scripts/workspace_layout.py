"""Repository layout helpers for canonical and compatibility workspaces.

This module centralizes repository path resolution so scripts stop hard-coding
stale directory names. The source of truth is ``workspace_manifest.json``. The
manifest may describe either a split-snapshot workspace or a single-root source
release where the canonical root is the repository root itself.
"""

from dataclasses import dataclass
from pathlib import Path
import json
import re
import sys
from typing import Any, Iterable

_SCRIPT_DIR = Path(__file__).resolve().parent


def _candidate_ros2_roots() -> tuple[Path, ...]:
    return (
        _SCRIPT_DIR.parent / 'ros2_ws' / 'src',
        _SCRIPT_DIR.parent.parent / 'ros2_ws' / 'src',
    )


def _extend_import_path() -> None:
    for ros2_root in _candidate_ros2_roots():
        if not ros2_root.exists():
            continue
        for pkg in ros2_root.iterdir():
            if pkg.is_dir() and str(pkg) not in sys.path:
                sys.path.insert(0, str(pkg))


_extend_import_path()

try:
    from robot_utils.versioning import satisfies_engine_expression  # type: ignore
except Exception:
    _COMPARATOR_PATTERN = re.compile(r'^(>=|<=|>|<|=)?\s*(\d+(?:\.\d+)*)$')

    def _parse_version(value: str) -> tuple[int, ...]:
        match = re.search(r'\d+(?:\.\d+)*', str(value))
        if not match:
            return ()
        return tuple(int(part) for part in match.group(0).split('.'))

    def _compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
        width = max(len(left), len(right))
        left_padded = left + (0,) * (width - len(left))
        right_padded = right + (0,) * (width - len(right))
        if left_padded < right_padded:
            return -1
        if left_padded > right_padded:
            return 1
        return 0

    def satisfies_engine_expression(version: str, expression: str) -> bool:
        current = _parse_version(version)
        if not current:
            return False
        normalized = str(expression or '').strip()
        if not normalized:
            return False
        for branch in normalized.split('||'):
            comparators = [item for item in branch.strip().split() if item]
            if not comparators:
                continue
            branch_ok = True
            for comparator_text in comparators:
                match = _COMPARATOR_PATTERN.match(comparator_text)
                if not match:
                    branch_ok = False
                    break
                operator = match.group(1) or '='
                target = _parse_version(match.group(2))
                relation = _compare_versions(current, target)
                if operator == '>=':
                    ok = relation >= 0
                elif operator == '<=':
                    ok = relation <= 0
                elif operator == '>':
                    ok = relation > 0
                elif operator == '<':
                    ok = relation < 0
                else:
                    ok = relation == 0
                if not ok:
                    branch_ok = False
                    break
            if branch_ok:
                return True
        return False


_REQUIRED_MANIFEST_KEYS = {
    'canonical_workspace_dir': str,
    'compatibility_workspace_dir': str,
    'workflow_path': str,
    'outer_readme_path': str,
    'esp_root': str,
    'stm_root': str,
}
_REQUIRED_SOURCE_RELEASE_KEYS = {
    'excluded_dir_names': list,
    'excluded_file_suffixes': list,
    'excluded_file_names': list,
    'excluded_part_suffixes': list,
}
_REQUIRED_COMPATIBILITY_KEYS = {
    'required_paths': list,
    'wrapper_pairs': list,
}


@dataclass(frozen=True, slots=True)
class WorkspaceLayout:
    """Resolved repository layout for one canonical workspace description."""

    repo_root: Path
    manifest_path: Path
    ubuntu_root: Path
    compatibility_root: Path
    compatibility_ubuntu_root: Path
    workflow_path: Path
    outer_readme_path: Path
    esp_root: Path
    stm_root: Path
    canonical_esp_root: Path
    canonical_stm_root: Path
    source_release: dict[str, Any]
    compatibility_shell: dict[str, Any]
    layout_mode: str
    uses_compatibility_shell: bool


def _find_manifest(anchor: Path) -> Path:
    resolved = anchor.resolve()
    search_roots: Iterable[Path]
    if resolved.is_dir():
        search_roots = (resolved, *resolved.parents)
    else:
        search_roots = (resolved.parent, *resolved.parent.parents)
    matches: list[Path] = []
    for candidate in search_roots:
        manifest = candidate / 'workspace_manifest.json'
        if manifest.is_file():
            matches.append(manifest)
    if not matches:
        raise RuntimeError(f'workspace_manifest.json not found above {anchor}')
    return matches[-1]


def _validate_mapping(name: str, payload: object, required_keys: dict[str, type]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError(f'{name} must be a JSON object')
    normalized = dict(payload)
    for key, expected_type in required_keys.items():
        value = normalized.get(key)
        if not isinstance(value, expected_type):
            raise RuntimeError(f'{name}.{key} must be {expected_type.__name__}')
    return normalized


def _validate_manifest(manifest: object, *, manifest_path: Path) -> dict[str, Any]:
    normalized = _validate_mapping('workspace_manifest', manifest, _REQUIRED_MANIFEST_KEYS)
    source_release = _validate_mapping(
        'workspace_manifest.source_release',
        normalized.get('source_release'),
        _REQUIRED_SOURCE_RELEASE_KEYS,
    )
    compatibility_shell = _validate_mapping(
        'workspace_manifest.compatibility_shell',
        normalized.get('compatibility_shell'),
        _REQUIRED_COMPATIBILITY_KEYS,
    )
    wrapper_pairs = compatibility_shell['wrapper_pairs']
    for index, entry in enumerate(wrapper_pairs):
        if not isinstance(entry, dict):
            raise RuntimeError(f'workspace_manifest.compatibility_shell.wrapper_pairs[{index}] must be an object')
        if not isinstance(entry.get('compatibility'), str) or not isinstance(entry.get('canonical'), str):
            raise RuntimeError(
                f'workspace_manifest.compatibility_shell.wrapper_pairs[{index}] must define string compatibility/canonical paths'
            )
    normalized['source_release'] = source_release
    normalized['compatibility_shell'] = compatibility_shell
    normalized['manifest_path'] = str(manifest_path)
    return normalized


def _load_manifest(anchor: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = _find_manifest(anchor)
    payload = json.loads(manifest_path.read_text(encoding='utf-8'))
    return manifest_path, _validate_manifest(payload, manifest_path=manifest_path)


def _resolve_required_path(repo_root: Path, relative_path: str, *, field_name: str) -> Path:
    resolved = (repo_root / relative_path).resolve()
    if not resolved.exists():
        raise RuntimeError(
            f'{field_name} resolved to a missing path: {resolved} '            f'(manifest={repo_root / "workspace_manifest.json"})'
        )
    return resolved


def resolve_workspace_layout(anchor: Path) -> WorkspaceLayout:
    """Resolve canonical and compatibility paths from the manifest.

    Args:
        anchor: Any file or directory inside the current repository.

    Returns:
        One resolved :class:`WorkspaceLayout`.

    Raises:
        RuntimeError: When the manifest is missing, structurally invalid, or
            resolves to non-existent repository paths.
        json.JSONDecodeError: When the manifest file is not valid JSON.

    Boundary behavior:
        The outermost manifest above ``anchor`` wins so nested directories cannot
        silently override the repository source of truth.
    """
    manifest_path, manifest = _load_manifest(anchor)
    repo_root = manifest_path.parent.resolve()
    ubuntu_root = _resolve_required_path(repo_root, manifest['canonical_workspace_dir'], field_name='workspace_manifest.canonical_workspace_dir')
    compatibility_ubuntu_root = _resolve_required_path(
        repo_root,
        manifest['compatibility_workspace_dir'],
        field_name='workspace_manifest.compatibility_workspace_dir',
    )
    workflow_path = _resolve_required_path(repo_root, manifest['workflow_path'], field_name='workspace_manifest.workflow_path')
    outer_readme_path = _resolve_required_path(repo_root, manifest['outer_readme_path'], field_name='workspace_manifest.outer_readme_path')
    esp_root = _resolve_required_path(repo_root, manifest['esp_root'], field_name='workspace_manifest.esp_root')
    stm_root = _resolve_required_path(repo_root, manifest['stm_root'], field_name='workspace_manifest.stm_root')
    canonical_esp_root = _resolve_required_path(ubuntu_root, manifest['esp_root'], field_name='workspace_manifest.canonical_esp_root')
    canonical_stm_root = _resolve_required_path(ubuntu_root, manifest['stm_root'], field_name='workspace_manifest.canonical_stm_root')
    layout_mode = str(manifest.get('layout_mode', 'split_snapshot')).strip() or 'split_snapshot'
    uses_compatibility_shell = ubuntu_root != repo_root or compatibility_ubuntu_root != repo_root
    return WorkspaceLayout(
        repo_root=repo_root,
        manifest_path=manifest_path,
        ubuntu_root=ubuntu_root,
        compatibility_root=repo_root,
        compatibility_ubuntu_root=compatibility_ubuntu_root,
        workflow_path=workflow_path,
        outer_readme_path=outer_readme_path,
        esp_root=esp_root,
        stm_root=stm_root,
        canonical_esp_root=canonical_esp_root,
        canonical_stm_root=canonical_stm_root,
        source_release=dict(manifest.get('source_release', {})),
        compatibility_shell=dict(manifest.get('compatibility_shell', {})),
        layout_mode=layout_mode,
        uses_compatibility_shell=uses_compatibility_shell,
    )


def parse_frontend_engine_constraints(frontend_package_json: Path) -> dict[str, str]:
    payload = json.loads(frontend_package_json.read_text(encoding='utf-8'))
    engines = payload.get('engines', {})
    return {
        'node': str(engines.get('node', '')).strip(),
        'npm': str(engines.get('npm', '')).strip(),
    }


def satisfies_frontend_node_engine(version: str, expression: str) -> bool:
    return satisfies_engine_expression(str(version).lstrip('v'), expression)


def satisfies_frontend_npm_engine(version: str, expression: str) -> bool:
    return satisfies_engine_expression(version, expression)
