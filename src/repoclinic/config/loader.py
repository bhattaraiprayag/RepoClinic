"""Configuration loading and override resolution."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from repoclinic.config.models import AppConfig

DEFAULT_CONFIG_PATH = Path("config/settings.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Configuration file must deserialize to a mapping")
    return data


def apply_overrides(
    raw_config: dict[str, Any],
    env: Mapping[str, str],
    cli_overrides: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Apply precedence: CLI > env > YAML defaults."""
    merged = dict(raw_config)
    env_default_profile = env.get("REPOCLINIC_DEFAULT_PROVIDER_PROFILE")
    if env_default_profile:
        merged["default_provider_profile"] = env_default_profile

    if cli_overrides:
        if cli_overrides.get("default_provider_profile"):
            merged["default_provider_profile"] = cli_overrides["default_provider_profile"]
        if cli_overrides.get("max_file_size_bytes") is not None:
            merged.setdefault("scan_policy", {})
            merged["scan_policy"]["max_file_size_bytes"] = cli_overrides["max_file_size_bytes"]
    return merged


def load_app_config(
    config_path: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
) -> AppConfig:
    """Load and validate central application config."""
    active_env = env or os.environ
    raw = _load_yaml(config_path or DEFAULT_CONFIG_PATH)
    merged = apply_overrides(raw, active_env, cli_overrides)
    return AppConfig.model_validate(merged)
