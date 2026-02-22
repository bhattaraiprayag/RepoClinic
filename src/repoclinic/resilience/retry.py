"""Retry and timeout execution helpers."""

from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """Retry/backoff policy."""

    max_attempts: int
    backoff_seconds: float
    jitter_seconds: float = 0.2


class RetryExecutor:
    """Execute callables with retries and optional timeout."""

    def __init__(
        self,
        policy: RetryPolicy,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        jitter_fn: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self.policy = policy
        self._sleep = sleep_fn
        self._jitter = jitter_fn

    def run(
        self,
        operation: Callable[[], T],
        *,
        stage_name: str,
        timeout_seconds: int | None = None,
    ) -> T:
        """Run operation with retries/backoff/jitter and optional timeout."""
        if self.policy.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        last_error: Exception | None = None
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                return self._run_once(operation, timeout_seconds=timeout_seconds)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= self.policy.max_attempts:
                    break
                delay = self._backoff_delay(attempt)
                self._sleep(delay)

        assert last_error is not None
        raise RuntimeError(
            f"{stage_name} failed after {self.policy.max_attempts} attempt(s): {last_error}"
        ) from last_error

    def _run_once(
        self,
        operation: Callable[[], T],
        *,
        timeout_seconds: int | None,
    ) -> T:
        if timeout_seconds is None:
            return operation()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(operation)
            try:
                return future.result(timeout=timeout_seconds)
            except FuturesTimeoutError as exc:
                raise TimeoutError(
                    f"Operation timed out after {timeout_seconds} second(s)"
                ) from exc

    def _backoff_delay(self, attempt: int) -> float:
        base_delay = self.policy.backoff_seconds * (2 ** (attempt - 1))
        jitter = self._jitter(0.0, self.policy.jitter_seconds)
        return max(0.0, base_delay + jitter)
