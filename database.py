"""SQLite: журнал загрузок и служебные метаданные."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Каталог data/ рядом с корнем проекта
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "app.sqlite3"


def get_connection() -> sqlite3.Connection:
    """Открывает соединение с БД (файл создаётся при первом обращении)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Создаёт таблицы, если их ещё нет.

    uploads — история загрузок CSV (имя файла, время, число строк, список колонок).
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                columns_json TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def log_upload(filename: str, row_count: int, columns: list[str]) -> int:
    """
    Записывает факт загрузки файла. Возвращает id записи.
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO uploads (filename, uploaded_at, row_count, columns_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                filename,
                datetime.now(timezone.utc).isoformat(),
                row_count,
                json.dumps(columns, ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        conn.close()


def recent_uploads(limit: int = 20) -> list[dict[str, Any]]:
    """Последние записи журнала загрузок (для отображения в UI)."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, filename, uploaded_at, row_count, columns_json
            FROM uploads
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "filename": r["filename"],
                    "uploaded_at": r["uploaded_at"],
                    "row_count": r["row_count"],
                    "columns": json.loads(r["columns_json"]),
                }
            )
        return out
    finally:
        conn.close()
