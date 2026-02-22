"""Token budgeting utilities."""

from __future__ import annotations

import tiktoken


class TokenBudgetExceededError(ValueError):
    """Raised when content exceeds the assigned token budget."""


class TokenBudgeter:
    """Utility for deterministic token counting and enforcement."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        try:
            self._encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        """Return token count for text."""
        return len(self._encoding.encode(text))

    def ensure_within_budget(self, text: str, budget: int) -> int:
        """Validate token count against a hard budget."""
        token_count = self.count(text)
        if token_count > budget:
            raise TokenBudgetExceededError(
                f"Token budget exceeded: {token_count} > {budget}"
            )
        return token_count
