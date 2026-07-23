import sqlite3
import uuid

from app.db.connection import get_connection
from app.errors import ApiError


def create_session() -> str:
    session_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute("INSERT INTO sessions (id) VALUES (?)", (session_id,))
        conn.commit()
    finally:
        conn.close()
    return session_id


def get_session(sid: str, conn: sqlite3.Connection | None = None) -> sqlite3.Row:
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        if row is None:
            raise ApiError(404, "session_not_found", f"Session '{sid}' not found.")
        return row
    finally:
        if owns_conn:
            conn.close()


def get_system_prompt(sid: str) -> str:
    conn = get_connection()
    try:
        session = get_session(sid, conn)
        return session["system_prompt"] or ""
    finally:
        conn.close()


def set_system_prompt(sid: str, text: str) -> None:
    conn = get_connection()
    try:
        get_session(sid, conn)
        conn.execute(
            "UPDATE sessions SET system_prompt = ? WHERE id = ?", (text, sid)
        )
        conn.commit()
    finally:
        conn.close()
