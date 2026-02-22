"""Token budget utility tests."""

from __future__ import annotations

import pytest

from repoclinic.config.token_budget import TokenBudgetExceededError, TokenBudgeter


def test_token_budget_overflow_raises() -> None:
    """Overflow should raise a deterministic exception."""
    budgeter = TokenBudgeter("gpt-4o-mini")
    oversized_text = "token " * 500
    with pytest.raises(TokenBudgetExceededError):
        budgeter.ensure_within_budget(oversized_text, budget=5)
