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
    api_key_env: "LM_STUDIO_AUTH_TOKEN"
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
    api_key_env: "LM_STUDIO_AUTH_TOKEN"
    max_tokens: 1024
    capabilities:
      context_window: 16384
""".strip(),
    )

    with pytest.raises(ValueError):
        load_app_config(config_path, env={})


def test_lmstudio_env_overrides_apply(tmp_path: Path) -> None:
    """LM Studio base URL and model should be overrideable via env."""
    config_path = _write_config(
        tmp_path,
        """
schema_version: "1.0.0"
default_provider_profile: "lm-studio-default"
provider_profiles:
  lm-studio-default:
    provider_type: "lm_studio"
    model: "default-model"
    api_key_env: "LM_STUDIO_AUTH_TOKEN"
    base_url: "http://127.0.0.1:1234/v1"
    max_tokens: 1024
    capabilities:
      context_window: 16384
""".strip(),
    )
    config = load_app_config(
        config_path,
        env={
            "LM_STUDIO_BASE_URL": "http://192.168.1.70:1234/v1",
            "LM_STUDIO_MODEL": "qwen/qwen3-vl-30b",
        },
    )
    profile = config.provider_profiles["lm-studio-default"]
    assert profile.base_url == "http://192.168.1.70:1234/v1"
    assert profile.model == "lm_studio/qwen/qwen3-vl-30b"


def test_lmstudio_api_base_alias_override_applies(tmp_path: Path) -> None:
    """LM_STUDIO_API_BASE should work as alias for base URL override."""
    config_path = _write_config(
        tmp_path,
        """
schema_version: "1.0.0"
default_provider_profile: "lm-studio-default"
provider_profiles:
  lm-studio-default:
    provider_type: "lm_studio"
    model: "default-model"
    api_key_env: "LM_STUDIO_AUTH_TOKEN"
    base_url: "http://127.0.0.1:1234/v1"
    max_tokens: 1024
    capabilities:
      context_window: 16384
""".strip(),
    )
    config = load_app_config(
        config_path,
        env={"LM_STUDIO_API_BASE": "http://localhost:1234/v1"},
    )
    profile = config.provider_profiles["lm-studio-default"]
    assert profile.base_url == "http://localhost:1234/v1"
