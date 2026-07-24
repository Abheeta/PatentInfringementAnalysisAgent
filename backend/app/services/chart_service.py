import csv
import io
import sqlite3

from app.ai.row_display import to_display_id
from app.db.connection import get_connection
from app.errors import ApiError
from app.services.session_service import get_session


def _decode(file_bytes: bytes, malformed_code: str, malformed_message: str) -> str:
    try:
        return file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError(400, malformed_code, malformed_message)


def parse_chart_csv(sid: str, file_bytes: bytes) -> None:
    conn = get_connection()
    try:
        session = get_session(sid, conn)
        if session["chart_uploaded"]:
            raise ApiError(
                409,
                "chart_already_exists",
                "A chart has already been uploaded for this session. "
                "Start a new session to upload a different chart.",
            )

        text = _decode(
            file_bytes, "malformed_csv", "Could not decode file as UTF-8 text."
        )
        reader = csv.reader(io.StringIO(text))
        data_rows = list(reader)[1:]  # skip header row

        parsed = []
        for i, row in enumerate(data_rows, start=2):
            if len(row) == 0 or (len(row) == 1 and row[0].strip() == ""):
                continue
            if len(row) != 3:
                raise ApiError(
                    400,
                    "malformed_csv",
                    f"Row {i} has {len(row)} columns, expected 3.",
                )
            parsed.append(row)

        for claim_element, product_feature, ai_reasoning in parsed:
            conn.execute(
                """INSERT INTO rows (session_id, claim_element, product_feature, ai_reasoning)
                   VALUES (?, ?, ?, ?)""",
                (sid, claim_element, product_feature, ai_reasoning),
            )

        conn.execute(
            "UPDATE sessions SET chart_uploaded = 1 WHERE id = ?", (sid,)
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "claim_element": row["claim_element"],
        "product_feature": row["product_feature"],
        "ai_reasoning": row["ai_reasoning"],
        "confidence": row["confidence"],
        "flagged": bool(row["flagged"]),
        "pending_value": row["pending_value"],
        "pending_reasoning": row["pending_reasoning"],
        "pending_confidence": row["pending_confidence"],
        "previous_product_feature": row["previous_product_feature"],
        "previous_ai_reasoning": row["previous_ai_reasoning"],
        "previous_confidence": row["previous_confidence"],
    }


def _display_offset(conn: sqlite3.Connection, sid: str) -> int | None:
    row = conn.execute(
        "SELECT MIN(id) AS min_id FROM rows WHERE session_id = ?", (sid,)
    ).fetchone()
    return row["min_id"]


def _display_id(conn: sqlite3.Connection, sid: str, row_id: int) -> int:
    offset = _display_offset(conn, sid)
    return row_id if offset is None else to_display_id(offset, row_id)


def get_display_offset(sid: str) -> int:
    conn = get_connection()
    try:
        return _display_offset(conn, sid)
    finally:
        conn.close()


def get_rows(sid: str) -> list[dict]:
    conn = get_connection()
    try:
        session = get_session(sid, conn)
        if not session["chart_uploaded"]:
            raise ApiError(
                400, "chart_not_uploaded", "Upload a chart before viewing it."
            )
        rows = conn.execute(
            "SELECT * FROM rows WHERE session_id = ? ORDER BY id", (sid,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def _get_row(conn: sqlite3.Connection, sid: str, row_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM rows WHERE id = ? AND session_id = ?", (row_id, sid)
    ).fetchone()
    if row is None:
        raise ApiError(
            404,
            "row_not_found",
            f"Row {_display_id(conn, sid, row_id)} not found in this session.",
        )
    return row


def get_row(sid: str, row_id: int) -> dict:
    conn = get_connection()
    try:
        row = _get_row(conn, sid, row_id)
        return _row_to_dict(row)
    finally:
        conn.close()


def apply_classifications(sid: str, classifications: list[dict]) -> None:
    conn = get_connection()
    try:
        for item in classifications:
            conn.execute(
                "UPDATE rows SET confidence = ? WHERE id = ? AND session_id = ?",
                (item["confidence"], item["row_id"], sid),
            )
        conn.commit()
    finally:
        conn.close()


def finalize_generate(sid: str, opening_content: str) -> dict:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO chat_messages (session_id, role, content, row_id)
               VALUES (?, 'assistant', ?, NULL)""",
            (sid, opening_content),
        )
        message_id = cursor.lastrowid
        conn.execute("UPDATE sessions SET generated = 1 WHERE id = ?", (sid,))
        conn.commit()
        message = conn.execute(
            "SELECT * FROM chat_messages WHERE id = ?", (message_id,)
        ).fetchone()
        return {
            "id": message["id"],
            "role": message["role"],
            "content": message["content"],
            "row_id": message["row_id"],
            "created_at": message["created_at"],
        }
    finally:
        conn.close()


def set_pending(row_id: int, value: str, reasoning: str, confidence: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE rows SET pending_value = ?, pending_reasoning = ?,
               pending_confidence = ? WHERE id = ?""",
            (value, reasoning, confidence, row_id),
        )
        conn.commit()
    finally:
        conn.close()


def accept(sid: str, row_id: int) -> None:
    conn = get_connection()
    try:
        row = _get_row(conn, sid, row_id)
        if row["pending_value"] is None:
            raise ApiError(
                409,
                "no_pending_proposal",
                f"Row {_display_id(conn, sid, row_id)} has no pending proposal to accept.",
            )
        conn.execute(
            """UPDATE rows SET
                 previous_product_feature = ?,
                 previous_ai_reasoning = ?,
                 previous_confidence = ?,
                 product_feature = ?,
                 ai_reasoning = ?,
                 confidence = ?,
                 pending_value = NULL,
                 pending_reasoning = NULL,
                 pending_confidence = NULL
               WHERE id = ?""",
            (
                row["product_feature"],
                row["ai_reasoning"],
                row["confidence"],
                row["pending_value"],
                row["pending_reasoning"],
                row["pending_confidence"],
                row_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def reject(sid: str, row_id: int) -> None:
    conn = get_connection()
    try:
        row = _get_row(conn, sid, row_id)
        if row["pending_value"] is None:
            raise ApiError(
                409,
                "no_pending_proposal",
                f"Row {_display_id(conn, sid, row_id)} has no pending proposal to reject.",
            )
        conn.execute(
            """UPDATE rows SET pending_value = NULL, pending_reasoning = NULL,
               pending_confidence = NULL WHERE id = ?""",
            (row_id,),
        )
        conn.commit()
    finally:
        conn.close()


def undo(sid: str, row_id: int) -> None:
    conn = get_connection()
    try:
        row = _get_row(conn, sid, row_id)
        if row["previous_product_feature"] is None:
            raise ApiError(
                409,
                "no_undo_available",
                f"Row {_display_id(conn, sid, row_id)} has no previous value to undo to.",
            )
        conn.execute(
            """UPDATE rows SET
                 product_feature = ?,
                 ai_reasoning = ?,
                 confidence = ?,
                 previous_product_feature = NULL,
                 previous_ai_reasoning = NULL,
                 previous_confidence = NULL
               WHERE id = ?""",
            (
                row["previous_product_feature"],
                row["previous_ai_reasoning"],
                row["previous_confidence"],
                row_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def set_flagged(sid: str, row_id: int) -> None:
    conn = get_connection()
    try:
        row = _get_row(conn, sid, row_id)
        if row["flagged"]:
            raise ApiError(
                409,
                "already_flagged",
                f"Row {_display_id(conn, sid, row_id)} is already awaiting your "
                "description of the issue.",
            )
        blocking = conn.execute(
            "SELECT id FROM rows WHERE session_id = ? AND flagged = 1", (sid,)
        ).fetchone()
        if blocking is not None:
            raise ApiError(
                409,
                "already_flagged",
                f"Row {_display_id(conn, sid, blocking['id'])} is already "
                "awaiting your description of the issue — resolve it before "
                "flagging another row.",
            )
        conn.execute("UPDATE rows SET flagged = 1 WHERE id = ?", (row_id,))
        conn.commit()
    finally:
        conn.close()


def clear_flagged(row_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE rows SET flagged = 0 WHERE id = ?", (row_id,))
        conn.commit()
    finally:
        conn.close()
