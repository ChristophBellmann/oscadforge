from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


class ConfigError(RuntimeError):
    """Raised when a config file cannot be parsed or merged."""


def deep_merge(base: Any, incoming: Any) -> Any:
    if isinstance(base, dict) and isinstance(incoming, Mapping):
        merged = {**base}
        for key, value in incoming.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged
    if isinstance(base, list) and isinstance(incoming, list):
        return base + incoming
    return copy.deepcopy(incoming)


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}") from exc
    if not isinstance(data, Mapping):
        raise ConfigError(f"Config root in {path} must be a mapping")
    return dict(data)


def load_yaml_string(content: str) -> dict:
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise ConfigError("Invalid YAML from stdin") from exc
    if not isinstance(data, Mapping):
        raise ConfigError("Config root from stdin must be a mapping")
    return dict(data)


def merge_dicts(dicts: Iterable[Mapping[str, Any]]) -> dict:
    merged: dict[str, Any] = {}
    for data in dicts:
        merged = deep_merge(merged, data)
    return merged


def load_and_merge(paths: Iterable[Path]) -> dict:
    dicts = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(path)
        dicts.append(load_yaml(path))
    return merge_dicts(dicts)
