"""Phase 8 tracing integration tests."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any, cast

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
        self.started_spans: list[_FakeObservation] = []
        self.started_observations: list[_FakeObservation] = []
        self.flushed = False

    def start_span(self, **kwargs: Any) -> "_FakeObservation":
        observation = _FakeObservation(
            name=kwargs["name"],
            trace_context=kwargs.get("trace_context"),
            input_payload=kwargs.get("input"),
            output_payload=kwargs.get("output"),
            metadata=kwargs.get("metadata"),
        )
        self.started_spans.append(observation)
        return observation

    def start_as_current_observation(self, **kwargs: Any) -> "_FakeObservationContext":
        observation = _FakeObservation(
            name=kwargs["name"],
            trace_context=kwargs.get("trace_context"),
            input_payload=kwargs.get("input"),
            output_payload=kwargs.get("output"),
            metadata=kwargs.get("metadata"),
        )
        self.started_observations.append(observation)
        return _FakeObservationContext(observation)

    def flush(self) -> None:
        self.flushed = True


class _FakeObservation:
    def __init__(
        self,
        *,
        name: str,
        trace_context: dict[str, str] | None = None,
        input_payload: Any = None,
        output_payload: Any = None,
        metadata: Any = None,
    ) -> None:
        self.name = name
        self.trace_context = trace_context or {}
        self.input = input_payload
        self.output = output_payload
        self.metadata = metadata
        self.id = f"{name}-id"
        self.ended = False
        self.updates: list[dict[str, Any]] = []

    def update(self, **kwargs: Any) -> "_FakeObservation":
        self.updates.append(kwargs)
        if "input" in kwargs:
            self.input = kwargs["input"]
        if "output" in kwargs:
            self.output = kwargs["output"]
        if "metadata" in kwargs:
            self.metadata = kwargs["metadata"]
        return self

    def end(self) -> "_FakeObservation":
        self.ended = True
        return self


class _FakeObservationContext:
    def __init__(self, observation: _FakeObservation) -> None:
        self._observation = observation

    def __enter__(self) -> _FakeObservation:
        return self._observation

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        self._observation.end()
        return False


def _build_langfuse_tracer(monkeypatch: MonkeyPatch) -> tracing_module.LangfuseTracer:
    monkeypatch.setitem(
        sys.modules, "langfuse", SimpleNamespace(Langfuse=_FakeLangfuse)
    )
    return tracing_module.LangfuseTracer(
        {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_HOST": "http://localhost:3000",
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
        }
    )


def test_langfuse_tracer_prefers_langfuse_base_url(monkeypatch: MonkeyPatch) -> None:
    """LANGFUSE_BASE_URL should take precedence when both endpoint vars are set."""
    tracer = _build_langfuse_tracer(monkeypatch)
    client = cast(_FakeLangfuse, tracer._client)
    assert isinstance(client, _FakeLangfuse)
    assert client.kwargs["host"] == "https://cloud.langfuse.com"


def test_langfuse_tracer_records_run_input_and_output(
    monkeypatch: MonkeyPatch,
) -> None:
    """Run observations should keep payloads and close after finish_run."""
    tracer = _build_langfuse_tracer(monkeypatch)
    client = cast(_FakeLangfuse, tracer._client)

    tracer.start_run(
        run_id="run-123",
        metadata={"status": "running"},
        input_payload={"repo": "sample"},
    )
    run_observation = client.started_spans[0]
    assert run_observation.name == "repoclinic-run"
    assert run_observation.input == {"repo": "sample"}

    tracer.finish_run(
        run_id="run-123",
        metadata={"status": "completed"},
        output_payload={"result": "ok"},
    )
    assert run_observation.ended is True
    assert run_observation.updates[-1]["output"] == {"result": "ok"}


def test_langfuse_tracer_tracks_stage_lifecycle(monkeypatch: MonkeyPatch) -> None:
    """Stage observations should start on running and finish with output payloads."""
    tracer = _build_langfuse_tracer(monkeypatch)
    client = cast(_FakeLangfuse, tracer._client)

    tracer.start_run(
        run_id="run-123",
        metadata={"status": "running"},
        input_payload={"repo": "sample"},
    )
    root_observation = client.started_spans[0]
    tracer.record_stage(
        run_id="run-123",
        stage="scanner",
        metadata={"status": "running"},
        input_payload={"files": 10},
    )
    stage_observation = client.started_spans[1]
    assert stage_observation.name == "stage:scanner"
    assert stage_observation.trace_context["parent_span_id"] == root_observation.id

    tracer.record_stage(
        run_id="run-123",
        stage="scanner",
        metadata={"status": "completed"},
        output_payload={"findings": 5},
    )
    assert stage_observation.ended is True
    assert stage_observation.updates[-1]["output"] == {"findings": 5}
