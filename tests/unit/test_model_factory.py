"""Model factory tests for phase 2."""

from __future__ import annotations

from typing import Any

import pytest

import repoclinic.config.model_factory as model_factory_module
from repoclinic.config.model_factory import ModelFactory
from repoclinic.config.models import AppConfig


def _build_openai_config(max_tokens: int = 1024, context_window: int = 4096) -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0.0",
            "default_provider_profile": "openai-default",
            "provider_profiles": {
                "openai-default": {
                    "provider_type": "openai",
                    "model": "gpt-4.1",
                    "api_key_env": "OPENAI_API_KEY",
                    "max_tokens": max_tokens,
                    "capabilities": {
                        "context_window": context_window,
                        "supports_structured_output": True,
                        "retries": 3,
                    },
                }
            },
        }
    )


def _build_lmstudio_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0.0",
            "default_provider_profile": "lm-studio-default",
            "provider_profiles": {
                "lm-studio-default": {
                    "provider_type": "lm_studio",
                    "model": "qwen/qwen3-vl-30b",
                    "api_key_env": "LM_STUDIO_AUTH_TOKEN",
                    "base_url": "http://127.0.0.1:1234/v1/chat/completions",
                    "max_tokens": 1024,
                    "capabilities": {
                        "context_window": 16384,
                        "supports_structured_output": True,
                        "retries": 3,
                    },
                }
            },
        }
    )


class _FakeLLM:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_unknown_profile_name_is_rejected() -> None:
    """Factory should reject unknown profile names."""
    factory = ModelFactory(_build_openai_config())
    with pytest.raises(ValueError):
        factory.get_profile("missing-profile")


def test_missing_openai_api_key_is_rejected() -> None:
    """Factory must fail fast when OpenAI key is absent."""
    factory = ModelFactory(_build_openai_config())
    with pytest.raises(ValueError):
        factory.create_llm(env={})


def test_unsupported_capability_window_is_rejected() -> None:
    """max_tokens cannot exceed context window."""
    with pytest.raises(ValueError):
        _build_openai_config(max_tokens=8192, context_window=4096)


def test_missing_lmstudio_token_is_rejected() -> None:
    """LM Studio profile must require auth token env variable."""
    factory = ModelFactory(_build_lmstudio_config())
    with pytest.raises(ValueError):
        factory.create_llm(env={})


def test_lmstudio_base_url_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    """LM Studio /chat/completions URL should normalize to API base URL."""
    monkeypatch.setattr(model_factory_module, "LLM", _FakeLLM)
    factory = ModelFactory(_build_lmstudio_config())
    llm = factory.create_llm(env={"LM_STUDIO_AUTH_TOKEN": "token-value"})
    assert llm.kwargs["base_url"] == "http://127.0.0.1:1234/v1"
    assert llm.kwargs["api_key"] == "token-value"
    assert llm.kwargs["model"] == "lm_studio/qwen/qwen3-vl-30b"


def test_lmstudio_api_key_alias_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory should accept LM_STUDIO_API_KEY as LiteLLM-compatible alias."""
    monkeypatch.setattr(model_factory_module, "LLM", _FakeLLM)
    factory = ModelFactory(_build_lmstudio_config())
    llm = factory.create_llm(env={"LM_STUDIO_API_KEY": "token-value"})
    assert llm.kwargs["api_key"] == "token-value"
