"""CrewAI-compatible model factory."""

from __future__ import annotations

from typing import Mapping

from crewai import LLM

from repoclinic.config.models import AppConfig, ProviderProfile
from repoclinic.schemas.enums import ProviderType


class ModelFactory:
    """Factory for provider-specific CrewAI LLM clients."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def get_profile(self, profile_name: str | None = None) -> ProviderProfile:
        """Resolve provider profile by name."""
        active_profile = profile_name or self._config.default_provider_profile
        profile = self._config.provider_profiles.get(active_profile)
        if profile is None:
            raise ValueError(f"Unknown provider profile: {active_profile}")
        if profile.max_tokens > profile.capabilities.context_window:
            raise ValueError(
                f"Profile '{active_profile}' max_tokens exceeds context window"
            )
        return profile

    def create_llm(
        self,
        *,
        profile_name: str | None = None,
        env: Mapping[str, str],
    ) -> LLM:
        """Create a CrewAI-compatible LLM client for the active profile."""
        profile = self.get_profile(profile_name)
        api_key: str | None = None
        base_url: str | None = profile.base_url
        model_name = profile.model

        if profile.provider_type == ProviderType.OPENAI:
            assert profile.api_key_env is not None
            api_key = env.get(profile.api_key_env)
            if not api_key:
                raise ValueError(f"Missing API key env var: {profile.api_key_env}")
        elif profile.provider_type == ProviderType.LM_STUDIO:
            if not base_url:
                raise ValueError("LM Studio profile must define base_url")
            assert profile.api_key_env is not None
            api_key = env.get(profile.api_key_env)
            if not api_key:
                api_key = env.get("LM_STUDIO_API_KEY")
            if not api_key:
                raise ValueError(
                    f"Missing LM Studio auth env var: {profile.api_key_env} (or LM_STUDIO_API_KEY)"
                )
            base_url = _normalize_lmstudio_base_url(base_url)
            model_name = _normalize_lmstudio_model(profile.model)

        return LLM(
            model=model_name,
            temperature=profile.temperature,
            seed=profile.seed,
            max_tokens=profile.max_tokens,
            timeout=profile.timeout_seconds,
            api_key=api_key,
            base_url=base_url,
        )


def _normalize_lmstudio_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        normalized = normalized[: -len("/chat/completions")]
    return normalized


def _normalize_lmstudio_model(model_name: str) -> str:
    normalized = model_name.strip()
    if normalized.startswith("lm_studio/"):
        return normalized
    if normalized.startswith("lm-studio/"):
        return f"lm_studio/{normalized[len('lm-studio/') :]}"
    return f"lm_studio/{normalized}"
