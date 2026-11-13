import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4


APP_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = Path(
    os.getenv("SIDEBAR_DATABASE_PATH", str(APP_ROOT / "translation.db"))
)
RESULTS_DIR = APP_ROOT / "outputs" / "history"
DEFAULT_USER = "default"

# TODO: replace the default user with an authenticated user ID when auth exists.


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with _connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sidebar_translation_history (
                id TEXT PRIMARY KEY,
                user TEXT NOT NULL,
                file_name TEXT NOT NULL,
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Done', 'Failed')),
                kind TEXT NOT NULL CHECK(kind IN ('text', 'document')),
                source_text TEXT,
                result_text TEXT,
                result_path TEXT,
                result_file_name TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sidebar_history_user_created
            ON sidebar_translation_history(user, created_at DESC);

            """
        )


def add_translation(
    *,
    user: str,
    file_name: str,
    source_language: str,
    target_language: str,
    status: str,
    kind: str,
    source_text: str | None = None,
    result_text: str | None = None,
    result_data: bytes | None = None,
    result_file_name: str | None = None,
    error_message: str | None = None,
) -> str:
    if status not in {"Done", "Failed"}:
        raise ValueError("Translation history status must be Done or Failed.")
    if kind not in {"text", "document"}:
        raise ValueError("Translation history kind must be text or document.")

    translation_id = uuid4().hex
    result_path = None
    output_path = None
    if result_data is not None:
        suffix = Path(result_file_name or "").suffix.lower()
        if suffix not in {".pdf", ".docx", ".pptx", ".xlsx", ".txt"}:
            suffix = ".bin"
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / f"{translation_id}{suffix}"
        output_path.write_bytes(result_data)
        result_path = str(output_path.resolve())

    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        with _connection() as connection:
            connection.execute(
                """
                INSERT INTO sidebar_translation_history (
                    id, user, file_name, source_language, target_language,
                    status, kind, source_text, result_text, result_path,
                    result_file_name, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    translation_id,
                    user,
                    file_name,
                    source_language,
                    target_language,
                    status,
                    kind,
                    source_text,
                    result_text,
                    result_path,
                    result_file_name,
                    error_message,
                    created_at,
                ),
            )
    except sqlite3.Error:
        if output_path is not None and output_path.exists():
            output_path.unlink()
        raise

    return translation_id


def list_translations(
    user: str,
    search: str = "",
    limit: int | None = None,
) -> list[dict[str, object]]:
    query = "SELECT * FROM sidebar_translation_history WHERE user = ?"
    parameters: list[object] = [user]
    if search.strip():
        pattern = f"%{search.strip()}%"
        query += (
            " AND (file_name LIKE ? COLLATE NOCASE"
            " OR source_language LIKE ? COLLATE NOCASE"
            " OR target_language LIKE ? COLLATE NOCASE)"
        )
        parameters.extend([pattern, pattern, pattern])
    query += " ORDER BY created_at DESC, rowid DESC"
    if limit is not None:
        query += " LIMIT ?"
        parameters.append(limit)

    with _connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def get_translation(user: str, translation_id: str) -> dict[str, object] | None:
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM sidebar_translation_history
            WHERE user = ? AND id = ?
            """,
            (user, translation_id),
        ).fetchone()
    return dict(row) if row is not None else None


def read_result_file(result_path: str) -> bytes:
    path = Path(result_path).resolve()
    results_root = RESULTS_DIR.resolve()
    try:
        path.relative_to(results_root)
    except ValueError as error:
        raise ValueError("History result path is outside the results folder.") from error
    return path.read_bytes()

