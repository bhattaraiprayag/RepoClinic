"""SQLite persistence for scanner stage artifacts."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import orjson

from repoclinic.schemas.scanner_models import ScannerOutput


class ScannerPersistence:
    """SQLite persistence helper for scanner outputs."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    resolved_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS scanner_outputs (
                    run_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS flow_transitions (
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    reason TEXT NOT NULL
                );
                """
            )

    def persist_scanner_output(
        self,
        *,
        output: ScannerOutput,
        resolved_path: Path,
    ) -> None:
        """Persist scanner output and run status."""
        now = datetime.now(UTC).isoformat()
        payload = output.model_dump(mode="json")
        payload_json = orjson.dumps(payload).decode("utf-8")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, schema_version, repo_name, resolved_path, status, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    schema_version=excluded.schema_version,
                    repo_name=excluded.repo_name,
                    resolved_path=excluded.resolved_path,
                    status=excluded.status,
                    finished_at=excluded.finished_at
                """,
                (
                    output.run_id,
                    output.schema_version,
                    output.repo_profile.repo_name,
                    str(resolved_path),
                    "scanner_completed",
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO scanner_outputs (run_id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(run_id) DO UPDATE SET payload_json=excluded.payload_json
                """,
                (output.run_id, payload_json),
            )
