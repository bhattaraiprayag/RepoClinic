"""Runtime environment loading helpers."""

from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv

_DISABLE_DOTENV_VALUES = {"1", "true", "yes", "on"}


def load_runtime_env(*, filename: str = ".env") -> bool:
    """Load .env from cwd/parents without overriding existing process env."""
    disabled = os.getenv("REPOCLINIC_DISABLE_DOTENV", "").strip().lower()
    if disabled in _DISABLE_DOTENV_VALUES:
        return False

    dotenv_path = find_dotenv(filename=filename, usecwd=True)
    if not dotenv_path:
        return False

    return bool(load_dotenv(dotenv_path=dotenv_path, override=False))
