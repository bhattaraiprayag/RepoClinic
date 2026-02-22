"""Phase 8 tracing integration tests."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

import repoclinic.observability.tracing as tracing_module
from repoclinic.observability.tracing import NoOpTracer, create_tracer


def test_create_tracer_returns_noop_without_langfuse_keys() -> None:
    """Tracing should gracefully no-op when Langfuse credentials are absent."""
    tracer = create_tracer({})
    assert isinstance(tracer, NoOpTracer)


class _FakeLangfuse:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


def test_langfuse_tracer_prefers_langfuse_host(monkeypatch: MonkeyPatch) -> None:
    """LANGFUSE_HOST should take precedence when both host vars are set."""
    monkeypatch.setitem(sys.modules, "langfuse", SimpleNamespace(Langfuse=_FakeLangfuse))
    tracer = tracing_module.LangfuseTracer(
        {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_HOST": "http://localhost:3000",
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
        }
    )
    client = tracer._client
    assert isinstance(client, _FakeLangfuse)
    assert client.kwargs["host"] == "http://localhost:3000"
