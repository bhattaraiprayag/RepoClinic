"""Phase 8 tracing integration tests."""

from __future__ import annotations

from repoclinic.observability.tracing import NoOpTracer, create_tracer


def test_create_tracer_returns_noop_without_langfuse_keys() -> None:
    """Tracing should gracefully no-op when Langfuse credentials are absent."""
    tracer = create_tracer({})
    assert isinstance(tracer, NoOpTracer)
