"""Phase 8 retry executor tests."""

from __future__ import annotations

import time

import pytest

from repoclinic.resilience.retry import RetryExecutor, RetryPolicy


def test_retry_executor_retries_then_succeeds() -> None:
    """Executor should retry failed attempts and eventually return success."""
    attempts = {"count": 0}
    slept: list[float] = []

    def operation() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary failure")
        return "ok"

    executor = RetryExecutor(
        RetryPolicy(max_attempts=3, backoff_seconds=0.1, jitter_seconds=0.0),
        sleep_fn=slept.append,
        jitter_fn=lambda _a, _b: 0.0,
    )
    result = executor.run(operation, stage_name="retry-test")
    assert result == "ok"
    assert attempts["count"] == 3
    assert slept == [0.1, 0.2]


def test_retry_executor_timeout_raises() -> None:
    """Executor should raise a wrapped runtime error after timeout retries."""
    executor = RetryExecutor(
        RetryPolicy(max_attempts=1, backoff_seconds=0.0, jitter_seconds=0.0)
    )

    def operation() -> None:
        time.sleep(0.05)

    with pytest.raises(RuntimeError):
        executor.run(operation, stage_name="timeout-test", timeout_seconds=0)
