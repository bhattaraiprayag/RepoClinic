"""Flow transition logging for state tracking."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class FlowTransitionStore:
    """SQLite-backed transition log store."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS flow_transitions (
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
                """
            )

    def record_transition(
        self,
        *,
        run_id: str,
        node_id: str,
        from_state: str,
        to_state: str,
        reason: str,
    ) -> None:
        """Insert a transition record for a flow node."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO flow_transitions (run_id, node_id, from_state, to_state, timestamp, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    node_id,
                    from_state,
                    to_state,
                    datetime.now(UTC).isoformat(),
                    reason,
                ),
            )

    def list_transitions(self, run_id: str) -> list[tuple[str, str, str, str, str]]:
        """Return transitions in insertion order for a run."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT node_id, from_state, to_state, timestamp, reason
                FROM flow_transitions
                WHERE run_id = ?
                ORDER BY rowid ASC
                """,
                (run_id,),
            ).fetchall()
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]
