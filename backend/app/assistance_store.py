from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


def _database_path() -> Path:
    configured_path = os.getenv("ASSISTANCE_DB_PATH", "").strip()
    if configured_path:
        return Path(configured_path)
    return Path(__file__).resolve().parents[1] / "data" / "assistance_requests.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path, timeout=5)


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS assistance_requests (
            request_id TEXT PRIMARY KEY,
            submitted_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )


def save_request(request_id: str, submitted_at: str, payload_json: str) -> None:
    with closing(_connect()) as connection:
        with connection:
            _ensure_schema(connection)
            connection.execute(
                """
                INSERT INTO assistance_requests (request_id, submitted_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (request_id, submitted_at, payload_json),
            )


def load_requests() -> list[dict[str, Any]]:
    with closing(_connect()) as connection:
        with connection:
            _ensure_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT payload_json
                FROM assistance_requests
                ORDER BY submitted_at DESC, request_id DESC
                """
            ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]
