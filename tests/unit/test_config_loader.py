"""Configuration loading tests for phase 2."""

from __future__ import annotations

from pathlib import Path

import pytest

from repoclinic.config.loader import load_app_config


def _write_config(tmp_path: Path, content: str) -> Path:
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


def test_cli_overrides_env_and_yaml_defaults(tmp_path: Path) -> None:
    """CLI override should have highest precedence."""
    config_path = _write_config(
        tmp_path,
        """
schema_version: "1.0.0"
default_provider_profile: "openai-default"
provider_profiles:
  openai-default:
    provider_type: "openai"
    model: "gpt-4.1"
    api_key_env: "OPENAI_API_KEY"
    max_tokens: 1024
    capabilities:
      context_window: 128000
  lm-studio-default:
    provider_type: "lm_studio"
    model: "openai/local"
    base_url: "http://127.0.0.1:1234/v1"
    max_tokens: 1024
    capabilities:
      context_window: 16384
""".strip(),
    )

    config = load_app_config(
        config_path,
        env={"REPOCLINIC_DEFAULT_PROVIDER_PROFILE": "lm-studio-default"},
        cli_overrides={"default_provider_profile": "openai-default"},
    )
    assert config.default_provider_profile == "openai-default"


def test_invalid_profile_shape_is_rejected(tmp_path: Path) -> None:
    """LM Studio profile must define base_url."""
    config_path = _write_config(
        tmp_path,
        """
schema_version: "1.0.0"
default_provider_profile: "lm-studio-default"
provider_profiles:
  lm-studio-default:
    provider_type: "lm_studio"
    model: "openai/local"
    max_tokens: 1024
    capabilities:
      context_window: 16384
""".strip(),
    )

    with pytest.raises(ValueError):
        load_app_config(config_path)
