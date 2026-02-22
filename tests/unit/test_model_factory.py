"""Model factory tests for phase 2."""

from __future__ import annotations

import pytest

from repoclinic.config.model_factory import ModelFactory
from repoclinic.config.models import AppConfig


def _build_config(max_tokens: int = 1024, context_window: int = 4096) -> AppConfig:
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


def test_unknown_profile_name_is_rejected() -> None:
    """Factory should reject unknown profile names."""
    factory = ModelFactory(_build_config())
    with pytest.raises(ValueError):
        factory.get_profile("missing-profile")


def test_missing_openai_api_key_is_rejected() -> None:
    """Factory must fail fast when OpenAI key is absent."""
    factory = ModelFactory(_build_config())
    with pytest.raises(ValueError):
        factory.create_llm(env={})


def test_unsupported_capability_window_is_rejected() -> None:
    """max_tokens cannot exceed context window."""
    with pytest.raises(ValueError):
        _build_config(max_tokens=8192, context_window=4096)
