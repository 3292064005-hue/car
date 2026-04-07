from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import json

try:  # pragma: no cover - optional at runtime
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


class ConfigValidationError(ValueError):
    """Raised when configuration content is syntactically valid but semantically invalid."""


class StructuredConfigLoadError(ConfigValidationError):
    """Raised when a structured configuration file cannot be parsed under strict mode."""



def load_structured_file(path: str | None, default: Any, *, strict: bool = False, context: str = 'config') -> Any:
    """Load a YAML/JSON structured file.

    Args:
        path: Absolute or relative file path. ``None`` or empty values return ``default``.
        default: Fallback value returned for non-strict loads.
        strict: When ``True``, missing files and parse failures raise ``StructuredConfigLoadError``.
        context: Human-readable context used in raised error messages.

    Returns:
        Parsed YAML/JSON payload, or ``default`` when ``strict`` is ``False`` and loading fails.

    Raises:
        StructuredConfigLoadError: If ``strict`` is enabled and the file is missing or unparsable.
    """
    if not path:
        if strict:
            raise StructuredConfigLoadError(f'{context} path is empty')
        return default
    file_path = Path(path)
    if not file_path.exists():
        if strict:
            raise StructuredConfigLoadError(f'{context} file does not exist: {file_path}')
        return default
    text = file_path.read_text(encoding='utf-8')
    yaml_error: Exception | None = None
    if yaml is not None:
        try:
            data = yaml.safe_load(text)
            return default if data is None else data
        except Exception as exc:
            yaml_error = exc
    try:
        return json.loads(text)
    except Exception as json_error:
        if strict:
            detail = f'YAML={yaml_error}; JSON={json_error}' if yaml_error is not None else f'JSON={json_error}'
            raise StructuredConfigLoadError(f'{context} parse failed for {file_path}: {detail}') from json_error
        return default



def load_config_section(path: str | None, section: str, default: Any, *, strict: bool = False) -> Any:
    """Load a named section from a structured configuration file.

    Args:
        path: Structured file path.
        section: Section name to retrieve.
        default: Fallback value when the section is absent in non-strict mode.
        strict: Whether missing/invalid configuration should raise.

    Returns:
        Section payload or ``default``.

    Raises:
        StructuredConfigLoadError: If strict loading fails.
    """
    payload = load_structured_file(path, {}, strict=strict, context=f'{section} config')
    if isinstance(payload, dict) and section in payload:
        data = payload.get(section)
        return default if data is None else data
    return default



def require_keys(mapping: dict[str, Any], required: Iterable[str], *, context: str = 'config') -> None:
    missing = [key for key in required if key not in mapping]
    if missing:
        raise ConfigValidationError(f"{context} missing keys: {', '.join(missing)}")



def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged



def load_section_with_schema(
    path: str | None,
    section: str,
    default: Any,
    *,
    required_keys: Iterable[str] | None = None,
    strict: bool = False,
) -> Any:
    """Load and schema-check a configuration section.

    Args:
        path: Structured file path.
        section: Section name to retrieve.
        default: Fallback value in non-strict mode.
        required_keys: Optional required key list for mapping payloads.
        strict: Whether loading failures should raise.

    Returns:
        Section payload.

    Raises:
        StructuredConfigLoadError: If strict loading fails.
        ConfigValidationError: If the section violates required-key constraints.
    """
    data = load_config_section(path, section, default, strict=strict)
    if required_keys is not None and isinstance(data, dict):
        require_keys(data, required_keys, context=f'{section} section')
    return data
