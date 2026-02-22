"""Runtime .env loading tests."""

from __future__ import annotations

import os
from pathlib import Path

from repoclinic.runtime_env import load_runtime_env


def _write_env(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_load_runtime_env_reads_dotenv(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Runtime loader should populate env vars from .env when present."""
    _write_env(
        tmp_path / ".env",
        "LM_STUDIO_AUTH_TOKEN=from-dotenv\nLANGFUSE_HOST=http://localhost:3000\n",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LM_STUDIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.delenv("REPOCLINIC_DISABLE_DOTENV", raising=False)

    loaded = load_runtime_env()

    assert loaded is True
    assert os.environ["LM_STUDIO_AUTH_TOKEN"] == "from-dotenv"
    assert os.environ["LANGFUSE_HOST"] == "http://localhost:3000"


def test_load_runtime_env_does_not_override_existing(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Runtime loader should preserve already-exported process env values."""
    _write_env(tmp_path / ".env", "LM_STUDIO_AUTH_TOKEN=from-dotenv\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LM_STUDIO_AUTH_TOKEN", "from-shell")
    monkeypatch.delenv("REPOCLINIC_DISABLE_DOTENV", raising=False)

    loaded = load_runtime_env()

    assert loaded is True
    assert os.environ["LM_STUDIO_AUTH_TOKEN"] == "from-shell"


def test_load_runtime_env_can_be_disabled(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Runtime loader should no-op when explicit disable flag is set."""
    _write_env(tmp_path / ".env", "LM_STUDIO_AUTH_TOKEN=from-dotenv\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REPOCLINIC_DISABLE_DOTENV", "true")
    monkeypatch.delenv("LM_STUDIO_AUTH_TOKEN", raising=False)

    loaded = load_runtime_env()

    assert loaded is False
    assert "LM_STUDIO_AUTH_TOKEN" not in os.environ
