from __future__ import annotations

from pathlib import Path
from typing import Any

from config_types import ConfigError


def parse_strikes(raw: Any, path: str) -> tuple[int, ...]:
    if not isinstance(raw, list):
        raise ConfigError(f"{path} must be a list of ppem integers")
    if not raw:
        raise ConfigError(f"{path} must contain at least one ppem")
    strikes = tuple(require_int(value, f"{path}[]") for value in raw)
    if any(ppem < 1 or ppem > 127 for ppem in strikes):
        raise ConfigError(f"{path} values must be between 1 and 127")
    if len(set(strikes)) != len(strikes):
        raise ConfigError(f"{path} must not contain duplicate ppems")
    return strikes


def parse_table_tags(raw: Any, path: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ConfigError(f"{path} must be a list of exact OpenType table tags")
    tags: list[str] = []
    for value in raw:
        if not isinstance(value, str) or len(value) != 4:
            raise ConfigError(f"{path} entries must be exact 4-character table tags")
        tags.append(value)
    return tuple(tags)


def resolve_recipe_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


def require_mapping(raw: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must be a mapping")
    if not all(isinstance(key, str) for key in raw):
        raise ConfigError(f"{path} keys must be strings")
    return raw


def reject_unknown(data: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(f"{path} has unknown key(s): {', '.join(unknown)}")


def require_bool(raw: Any, path: str) -> bool:
    if type(raw) is not bool:
        raise ConfigError(f"{path} must be a boolean")
    return raw


def require_int(raw: Any, path: str) -> int:
    if type(raw) is not int:
        raise ConfigError(f"{path} must be an integer")
    return raw


def require_nonempty_str(raw: Any, path: str) -> str:
    value = optional_nonempty_str(raw, path)
    if value is None:
        raise ConfigError(f"{path} is required")
    return value


def optional_nonempty_str(raw: Any, path: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or raw == "":
        raise ConfigError(f"{path} must be a non-empty string")
    return raw

