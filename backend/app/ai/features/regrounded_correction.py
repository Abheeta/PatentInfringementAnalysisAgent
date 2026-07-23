"""Real implementation — ai-design-updated.md §6.5. Call signature unchanged
from the Phase 5 stub. Reuses §6.2's shape (including the answer/propose
intent split), with a verbatim-quote requirement scoped to the `propose`
path, and a converge-to-no_evidence_found fallback on a second failure
(instead of erroring, per §6.5).
"""

import logging

from app.ai import provider as ai_provider
from app.ai import schemas, validation
from app.ai.baseline_prompt import BASELINE_PROMPT
from app.ai.provider import LLMUnavailableError
from app.ai.validation import StructuredOutputError
from app.db.connection import get_connection
from app.services import evidence_service, session_service
from app.services.chart_service import get_row

logger = logging.getLogger(__name__)

_TASK_INSTRUCTION = (
    "Given this row's claim element, its current evidence and reasoning, "
    "the full evidence pool, and this row's own conversation history, the "
    "analyst has flagged this row's evidence as potentially wrong. If "
    "their latest message describes what's wrong, treat this as intent "
    "`propose`: find and quote the relevant line verbatim from the "
    "evidence pool — do not paraphrase; if no supporting line exists "
    "anywhere in the pool, state that no evidence was found. If their "
    "latest message is instead a question (e.g. asking why the row was "
    "flagged, or what the current evidence says), treat this as intent "
    "`answer` and answer directly - the row remains flagged until they "
    "actually describe the correction.\n\n"
    "Whichever intent you choose, you MUST fill in the fields it requires "
    "- never leave them null or empty:\n"
    "- intent `answer`: answer must be a real, non-empty answer written "
    "out in full.\n"
    "- intent `propose`, no evidence found: no_evidence_found must be "
    "true.\n"
    "- intent `propose`, evidence found: no_evidence_found must be false; "
    "proposed_value must be an exact verbatim quote from the evidence "
    "pool; reasoning must be real, non-empty text; confidence must be one "
    "of Strong/Moderate/Weak.\n"
    "Leave every field not listed for your chosen case null. Do not choose "
    "an intent and then leave its own required field(s) blank."
)

_RETRY_NOTE = (
    "Your previous response either wasn't found verbatim in the source "
    "text, or a required field for its chosen intent was left null/empty. "
    "If describing a correction (intent `propose`), quote the exact line "
    "from the evidence pool verbatim - do not paraphrase; if no such line "
    "exists, set no_evidence_found to true instead. If answering a "
    "question (intent `answer`), write out a real, non-empty answer."
)


def _row_thread(sid: str, row_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT role, content FROM chat_messages
               WHERE session_id = ? AND row_id = ? ORDER BY id""",
            (sid, row_id),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    finally:
        conn.close()


def _format_thread(thread: list[dict]) -> str:
    return "\n".join(f"{m['role']}: {m['content']}" for m in thread)


def correct(sid: str, row_id: int, message: str) -> dict:
    logger.info(
        "regrounded_correction: session=%s row=%d message_chars=%d",
        sid, row_id, len(message),
    )
    row = get_row(sid, row_id)
    evidence_pool = evidence_service.get_evidence_pool(sid)
    thread = _row_thread(sid, row_id)
    logger.info(
        "regrounded_correction: session=%s row=%d evidence_pool_chars=%d "
        "thread_messages=%d",
        sid, row_id, len(evidence_pool), len(thread),
    )

    system_prompt = session_service.get_system_prompt(sid)
    system_content = BASELINE_PROMPT
    if system_prompt:
        system_content += "\n\n" + system_prompt

    user_content = (
        f"{_TASK_INSTRUCTION}\n\n"
        f"Row {row_id}:\n"
        f"claim_element={row['claim_element']!r}\n"
        f"current_evidence={row['product_feature']!r}\n"
        f"current_reasoning={row['ai_reasoning']!r}\n"
        f"current_confidence={row['confidence']!r}\n\n"
        f"Evidence pool:\n{evidence_pool}\n\n"
        f"This row's conversation history:\n{_format_thread(thread)}\n\n"
        f"Analyst's current message:\n{message}"
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    schema = schemas.row_turn_schema(row_id)

    try:
        result = validation.call_with_retry(
            ai_provider.get_provider(),
            messages,
            schema,
            validation.validate_verbatim_quote(evidence_pool),
            _RETRY_NOTE,
        )
    except StructuredOutputError as exc:
        # The no-evidence-found fallback only makes sense on the `propose`
        # path (§6.5) — an `answer` response that fails the intent-pairing
        # check has no such fallback and goes through the normal error path.
        last = exc.last_result
        if last is not None and last.get("intent") == "answer":
            logger.warning(
                "regrounded_correction: session=%s row=%d answer path failed "
                "validation twice, no fallback available: %s",
                sid, row_id, exc,
            )
            raise LLMUnavailableError(
                f"Model could not produce a usable answer for row {row_id}: {exc}"
            )
        logger.warning(
            "regrounded_correction: session=%s row=%d propose path failed "
            "twice, converging to no_evidence_found: %s",
            sid, row_id, exc,
        )
        return {
            "row_id": row_id,
            "intent": "propose",
            "answer": None,
            "no_evidence_found": True,
            "proposed_value": None,
            "reasoning": None,
            "confidence": None,
        }
    logger.info(
        "regrounded_correction: session=%s row=%d resolved intent=%s",
        sid, row_id, result["intent"],
    )
    return result
