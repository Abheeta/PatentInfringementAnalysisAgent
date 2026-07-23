import logging

from app.ai.features import refinement_proposal, regrounded_correction, router
from app.db.connection import get_connection
from app.errors import ApiError
from app.services import chart_service
from app.services.session_service import get_session

logger = logging.getLogger(__name__)


def _insert_message(conn, sid: str, role: str, content: str, row_id: int | None) -> dict:
    cursor = conn.execute(
        """INSERT INTO chat_messages (session_id, role, content, row_id)
           VALUES (?, ?, ?, ?)""",
        (sid, role, content, row_id),
    )
    message = conn.execute(
        "SELECT * FROM chat_messages WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return {
        "id": message["id"],
        "role": message["role"],
        "content": message["content"],
        "row_id": message["row_id"],
        "created_at": message["created_at"],
    }


def _recent_history(conn, sid: str, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        """SELECT role, content, row_id FROM chat_messages
           WHERE session_id = ? ORDER BY id DESC LIMIT ?""",
        (sid, limit),
    ).fetchall()
    return [
        {"role": r["role"], "content": r["content"], "row_id": r["row_id"]}
        for r in reversed(rows)
    ]


def _run_row_turn(sid: str, row_id: int, content: str) -> tuple[str, bool]:
    """Returns (assistant_content, refresh_chart)."""
    row = chart_service.get_row(sid, row_id)

    if row["flagged"]:
        logger.info("chat_service: session=%s row=%d -> regrounded_correction (flagged)", sid, row_id)
        result = regrounded_correction.correct(sid, row_id, content)
    else:
        logger.info("chat_service: session=%s row=%d -> refinement_proposal", sid, row_id)
        result = refinement_proposal.propose(sid, row_id, content)

    if result["intent"] == "answer":
        # Answering a question about a flagged row doesn't resolve the flag
        # cycle — only a completed `propose` does (ai-design-updated.md §6.5).
        return result["answer"], False

    if result["no_evidence_found"]:
        if row["flagged"]:
            chart_service.clear_flagged(row_id)
        return (
            f"I couldn't find supporting evidence for row {row_id} in the "
            "uploaded docs. Can you upload another document or provide a URL?",
            False,
        )

    chart_service.set_pending(
        row_id, result["proposed_value"], result["reasoning"], result["confidence"]
    )
    if row["flagged"]:
        chart_service.clear_flagged(row_id)

    return f"Proposing an update to row {row_id}: {result['reasoning']}", True


def handle_message(sid: str, content: str, row_id: int | None) -> dict:
    if not content or not content.strip():
        raise ApiError(400, "empty_message", "Message content cannot be empty.")

    conn = get_connection()
    try:
        session = get_session(sid, conn)
        if not session["generated"]:
            raise ApiError(
                400, "not_generated_yet", "Run Generate before chatting."
            )

        if row_id is not None:
            chart_service.get_row(sid, row_id)  # raises row_not_found if invalid

        history = _recent_history(conn, sid)
        _insert_message(conn, sid, "user", content, row_id)
        conn.commit()
    finally:
        conn.close()

    resolved_row_id = row_id
    if resolved_row_id is None:
        logger.info("chat_service: session=%s no row_id given -> chat router", sid)
        resolution = router.resolve_row(sid, content, history)
        if resolution["intent"] in ("clarify", "answer"):
            reply = resolution["question"] if resolution["intent"] == "clarify" else resolution["answer"]
            conn = get_connection()
            try:
                message = _insert_message(conn, sid, "assistant", reply, None)
                conn.commit()
            finally:
                conn.close()
            return {"assistant_message": message, "refresh_chart": False}
        resolved_row_id = resolution["row_id"]
    else:
        logger.info("chat_service: session=%s row_id=%d given directly", sid, row_id)

    assistant_content, refresh_chart = _run_row_turn(sid, resolved_row_id, content)

    conn = get_connection()
    try:
        message = _insert_message(
            conn, sid, "assistant", assistant_content, resolved_row_id
        )
        conn.commit()
    finally:
        conn.close()

    return {"assistant_message": message, "refresh_chart": refresh_chart}


def get_history(sid: str) -> list[dict]:
    conn = get_connection()
    try:
        get_session(sid, conn)
        rows = conn.execute(
            """SELECT id, role, content, row_id, created_at FROM chat_messages
               WHERE session_id = ? ORDER BY id ASC""",
            (sid,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "row_id": r["row_id"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def post_flag_system_note(sid: str, row_id: int) -> dict:
    content = f"Row {row_id} flagged for re-scan. What's wrong with the current evidence?"
    conn = get_connection()
    try:
        message = _insert_message(conn, sid, "assistant", content, row_id)
        conn.commit()
    finally:
        conn.close()
    return message
