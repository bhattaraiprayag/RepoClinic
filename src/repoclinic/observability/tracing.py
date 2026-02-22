"""Langfuse tracing integration with safe fallback."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Mapping, Protocol

from repoclinic.security.redaction import redact_mapping

LOGGER = logging.getLogger(__name__)


class TracerProtocol(Protocol):
    """Tracer contract used by flow runner and flow stages."""

    def start_run(
        self,
        *,
        run_id: str,
        metadata: dict[str, Any],
        input_payload: Any | None = None,
    ) -> None:
        """Start a run trace."""

    def record_stage(
        self,
        *,
        run_id: str,
        stage: str,
        metadata: dict[str, Any],
        input_payload: Any | None = None,
        output_payload: Any | None = None,
    ) -> None:
        """Record stage-level metadata."""

    def finish_run(
        self,
        *,
        run_id: str,
        metadata: dict[str, Any],
        output_payload: Any | None = None,
    ) -> None:
        """Finalize a run trace."""

    def flush(self) -> None:
        """Flush/close tracing resources."""


class NoOpTracer:
    """No-op tracer implementation."""

    def start_run(
        self,
        *,
        run_id: str,
        metadata: dict[str, Any],
        input_payload: Any | None = None,
    ) -> None:
        del run_id, metadata, input_payload

    def record_stage(
        self,
        *,
        run_id: str,
        stage: str,
        metadata: dict[str, Any],
        input_payload: Any | None = None,
        output_payload: Any | None = None,
    ) -> None:
        del run_id, stage, metadata, input_payload, output_payload

    def finish_run(
        self,
        *,
        run_id: str,
        metadata: dict[str, Any],
        output_payload: Any | None = None,
    ) -> None:
        del run_id, metadata, output_payload

    def flush(self) -> None:
        return


class LangfuseTracer:
    """Langfuse-backed tracer."""

    def __init__(self, env: Mapping[str, str]) -> None:
        self._client: Any | None = None
        self._trace_context_by_run_id: dict[str, dict[str, str]] = {}
        self._run_observation_by_run_id: dict[str, Any] = {}
        self._stage_observation_by_key: dict[tuple[str, str], Any] = {}
        public_key = env.get("LANGFUSE_PUBLIC_KEY")
        secret_key = env.get("LANGFUSE_SECRET_KEY")
        host = env.get("LANGFUSE_BASE_URL") or env.get("LANGFUSE_HOST")
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

    def start_run(
        self,
        *,
        run_id: str,
        metadata: dict[str, Any],
        input_payload: Any | None = None,
    ) -> None:
        if self._client is None:
            return
        trace_context = {"trace_id": _trace_id(run_id)}
        self._trace_context_by_run_id[run_id] = trace_context
        try:
            previous_observation = self._run_observation_by_run_id.pop(run_id, None)
            if previous_observation is not None:
                previous_observation.end()
            self._run_observation_by_run_id[run_id] = self._client.start_span(
                trace_context=trace_context,
                name="repoclinic-run",
                input=redact_mapping(input_payload)
                if input_payload is not None
                else None,
                metadata=redact_mapping(metadata),
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Langfuse start_run failed: %s", exc)

    def record_stage(
        self,
        *,
        run_id: str,
        stage: str,
        metadata: dict[str, Any],
        input_payload: Any | None = None,
        output_payload: Any | None = None,
    ) -> None:
        if self._client is None:
            return
        trace_context = self._trace_context_by_run_id.get(
            run_id, {"trace_id": _trace_id(run_id)}
        ).copy()
        run_observation = self._run_observation_by_run_id.get(run_id)
        run_observation_id = getattr(run_observation, "id", None)
        if isinstance(run_observation_id, str):
            trace_context["parent_span_id"] = run_observation_id
        stage_key = (run_id, stage)
        redacted_metadata = redact_mapping(metadata)
        redacted_input = (
            redact_mapping(input_payload) if input_payload is not None else None
        )
        redacted_output = (
            redact_mapping(output_payload) if output_payload is not None else None
        )
        status = str(metadata.get("status", "")).lower()
        try:
            if status == "running":
                self._stage_observation_by_key[stage_key] = self._client.start_span(
                    trace_context=trace_context,
                    name=f"stage:{stage}",
                    input=redacted_input,
                    metadata=redacted_metadata,
                )
                return
            stage_observation = self._stage_observation_by_key.pop(stage_key, None)
            if stage_observation is None:
                with self._client.start_as_current_observation(
                    trace_context=trace_context,
                    name=f"stage:{stage}",
                    as_type="span",
                    input=redacted_input,
                    output=redacted_output,
                    metadata=redacted_metadata,
                ):
                    pass
                return
            stage_observation.update(
                input=redacted_input,
                output=redacted_output,
                metadata=redacted_metadata,
            )
            stage_observation.end()
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Langfuse record_stage failed: %s", exc)

    def finish_run(
        self,
        *,
        run_id: str,
        metadata: dict[str, Any],
        output_payload: Any | None = None,
    ) -> None:
        if self._client is None:
            return
        trace_context = self._trace_context_by_run_id.get(
            run_id, {"trace_id": _trace_id(run_id)}
        )
        redacted_metadata = redact_mapping(metadata)
        redacted_output = (
            redact_mapping(output_payload) if output_payload is not None else None
        )
        try:
            run_observation = self._run_observation_by_run_id.pop(run_id, None)
            if run_observation is None:
                with self._client.start_as_current_observation(
                    trace_context=trace_context,
                    name="repoclinic-run-complete",
                    as_type="span",
                    output=redacted_output,
                    metadata=redacted_metadata,
                ):
                    pass
            else:
                run_observation.update(
                    output=redacted_output,
                    metadata=redacted_metadata,
                )
                run_observation.end()
            for stage_key, stage_observation in list(
                self._stage_observation_by_key.items()
            ):
                stage_run_id, _ = stage_key
                if stage_run_id != run_id:
                    continue
                stage_observation.end()
                del self._stage_observation_by_key[stage_key]
            self._trace_context_by_run_id.pop(run_id, None)
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
