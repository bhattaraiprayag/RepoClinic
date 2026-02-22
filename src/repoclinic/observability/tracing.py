"""Langfuse tracing integration with safe fallback."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Mapping, Protocol

from repoclinic.security.redaction import redact_mapping

LOGGER = logging.getLogger(__name__)


class TracerProtocol(Protocol):
    """Tracer contract used by flow runner and flow stages."""

    def start_run(self, *, run_id: str, metadata: dict[str, Any]) -> None:
        """Start a run trace."""

    def record_stage(self, *, run_id: str, stage: str, metadata: dict[str, Any]) -> None:
        """Record stage-level metadata."""

    def finish_run(self, *, run_id: str, metadata: dict[str, Any]) -> None:
        """Finalize a run trace."""

    def flush(self) -> None:
        """Flush/close tracing resources."""


class NoOpTracer:
    """No-op tracer implementation."""

    def start_run(self, *, run_id: str, metadata: dict[str, Any]) -> None:
        del run_id, metadata

    def record_stage(self, *, run_id: str, stage: str, metadata: dict[str, Any]) -> None:
        del run_id, stage, metadata

    def finish_run(self, *, run_id: str, metadata: dict[str, Any]) -> None:
        del run_id, metadata

    def flush(self) -> None:
        return


class LangfuseTracer:
    """Langfuse-backed tracer."""

    def __init__(self, env: Mapping[str, str]) -> None:
        self._client: Any | None = None
        self._trace_context_by_run_id: dict[str, dict[str, str]] = {}
        public_key = env.get("LANGFUSE_PUBLIC_KEY")
        secret_key = env.get("LANGFUSE_SECRET_KEY")
        host = env.get("LANGFUSE_HOST") or env.get("LANGFUSE_BASE_URL")
        if not public_key or not secret_key:
            return

        try:
            from langfuse import Langfuse
        except ImportError:
            LOGGER.debug("langfuse package not installed; tracing disabled.")
            return

        kwargs: dict[str, Any] = {
            "public_key": public_key,
            "secret_key": secret_key,
        }
        if host:
            kwargs["host"] = host.rstrip("/")
        try:
            self._client = Langfuse(**kwargs)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to initialize Langfuse client: %s", exc)
            self._client = None

    @property
    def enabled(self) -> bool:
        """Return whether Langfuse tracing is active."""
        return self._client is not None

    def start_run(self, *, run_id: str, metadata: dict[str, Any]) -> None:
        if self._client is None:
            return
        trace_context = {"trace_id": _trace_id(run_id)}
        self._trace_context_by_run_id[run_id] = trace_context
        try:
            with self._client.start_as_current_observation(
                trace_context=trace_context,
                name="repoclinic-run",
                as_type="span",
                metadata=redact_mapping(metadata),
            ):
                pass
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Langfuse start_run failed: %s", exc)

    def record_stage(self, *, run_id: str, stage: str, metadata: dict[str, Any]) -> None:
        if self._client is None:
            return
        trace_context = self._trace_context_by_run_id.get(run_id, {"trace_id": _trace_id(run_id)})
        try:
            with self._client.start_as_current_observation(
                trace_context=trace_context,
                name=f"stage:{stage}",
                as_type="span",
                metadata=redact_mapping(metadata),
            ):
                pass
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Langfuse record_stage failed: %s", exc)

    def finish_run(self, *, run_id: str, metadata: dict[str, Any]) -> None:
        if self._client is None:
            return
        trace_context = self._trace_context_by_run_id.get(run_id, {"trace_id": _trace_id(run_id)})
        try:
            with self._client.start_as_current_observation(
                trace_context=trace_context,
                name="repoclinic-run-complete",
                as_type="span",
                metadata=redact_mapping(metadata),
            ):
                pass
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Langfuse finish_run failed: %s", exc)

    def flush(self) -> None:
        if self._client is None:
            return
        try:
            self._client.flush()
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Langfuse flush failed: %s", exc)


def create_tracer(env: Mapping[str, str]) -> TracerProtocol:
    """Create Langfuse tracer if configured, else no-op tracer."""
    tracer = LangfuseTracer(env)
    if not tracer.enabled:
        return NoOpTracer()
    return tracer


def _trace_id(run_id: str) -> str:
    """Derive deterministic 32-char trace IDs from run IDs."""
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:32]
