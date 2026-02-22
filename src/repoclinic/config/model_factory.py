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

        if profile.provider_type == ProviderType.OPENAI:
            assert profile.api_key_env is not None
            api_key = env.get(profile.api_key_env)
            if not api_key:
                raise ValueError(f"Missing API key env var: {profile.api_key_env}")
        elif profile.provider_type == ProviderType.LM_STUDIO:
            if not base_url:
                raise ValueError("LM Studio profile must define base_url")
            api_key = env.get(profile.api_key_env or "", "lm-studio")

        return LLM(
            model=profile.model,
            temperature=profile.temperature,
            seed=profile.seed,
            max_tokens=profile.max_tokens,
            timeout=profile.timeout_seconds,
            api_key=api_key,
            base_url=base_url,
        )
