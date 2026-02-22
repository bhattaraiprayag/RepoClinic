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
    _apply_lmstudio_env_overrides(merged, env)

    if cli_overrides:
        if cli_overrides.get("default_provider_profile"):
            merged["default_provider_profile"] = cli_overrides[
                "default_provider_profile"
            ]
        if cli_overrides.get("max_file_size_bytes") is not None:
            merged.setdefault("scan_policy", {})
            merged["scan_policy"]["max_file_size_bytes"] = cli_overrides[
                "max_file_size_bytes"
            ]
    return merged


def _apply_lmstudio_env_overrides(
    merged: dict[str, Any],
    env: Mapping[str, str],
) -> None:
    profiles = merged.get("provider_profiles")
    if not isinstance(profiles, dict):
        return
    lm_profile = profiles.get("lm-studio-default")
    if not isinstance(lm_profile, dict):
        return
    base_url_override = env.get("LM_STUDIO_BASE_URL") or env.get("LM_STUDIO_API_BASE")
    if base_url_override:
        lm_profile["base_url"] = base_url_override
    if env.get("LM_STUDIO_MODEL"):
        lm_profile["model"] = env["LM_STUDIO_MODEL"]
    if env.get("LM_STUDIO_API_KEY_ENV"):
        lm_profile["api_key_env"] = env["LM_STUDIO_API_KEY_ENV"]


def load_app_config(
    config_path: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
) -> AppConfig:
    """Load and validate central application config."""
    active_env = os.environ if env is None else env
    raw = _load_yaml(config_path or DEFAULT_CONFIG_PATH)
    merged = apply_overrides(raw, active_env, cli_overrides)
    return AppConfig.model_validate(merged)
