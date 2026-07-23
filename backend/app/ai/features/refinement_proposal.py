"""Real implementation — ai-design-updated.md §6.2 ("Row Turn", was
"Refinement Proposal"). Call signature unchanged from the Phase 5 stub.
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
    "the full evidence pool, and this row's own conversation history, "
    "decide whether the analyst's latest message is a question about this "
    "row (respond with intent `answer`, grounded in the evidence, without "
    "proposing a change) or a request for a change or improvement to this "
    "row's evidence (respond with intent `propose`: an improved evidence "
    "value + reasoning + confidence tier grounded in the evidence pool, or "
    "state that no supporting evidence was found). Address only this row. "
    "A short imperative message like \"refine\", \"improve this\", or "
    "\"make it stronger\" is a request for intent `propose`, not a "
    "question - only use intent `answer` when the analyst is actually "
    "asking something (e.g. \"why is this weak?\", \"what does the "
    "evidence say?\").\n\n"
    "Whichever intent you choose, you MUST fill in the fields it requires "
    "- never leave them null or empty:\n"
    "- intent `answer`: answer must be a real, non-empty answer written "
    "out in full.\n"
    "- intent `propose`, no evidence found: no_evidence_found must be "
    "true.\n"
    "- intent `propose`, evidence found: no_evidence_found must be false; "
    "proposed_value and reasoning must be real, non-empty text; "
    "confidence must be one of Strong/Moderate/Weak.\n"
    "Leave every field not listed for your chosen case null. Do not choose "
    "an intent and then leave its own required field(s) blank."
)

_RETRY_NOTE = (
    "Your previous response's required field(s) for its chosen intent were "
    "left null/empty. Re-read the rules: intent=answer requires a real "
    "non-empty answer written out in full; intent=propose requires a "
    "non-null no_evidence_found, and if no_evidence_found is false, "
    "proposed_value and reasoning must be real non-empty text with "
    "confidence one of Strong/Moderate/Weak. Pick one intent and actually "
    "write out the text its own fields require - do not leave them null."
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


def propose(sid: str, row_id: int, message: str) -> dict:
    logger.info(
        "refinement_proposal: session=%s row=%d message_chars=%d",
        sid, row_id, len(message),
    )
    row = get_row(sid, row_id)
    evidence_pool = evidence_service.get_evidence_pool(sid)
    thread = _row_thread(sid, row_id)
    logger.info(
        "refinement_proposal: session=%s row=%d evidence_pool_chars=%d "
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
            validation.validate_row_turn_pairing,
            _RETRY_NOTE,
        )
    except StructuredOutputError as exc:
        raise LLMUnavailableError(
            f"Model could not produce a usable response for row {row_id}: {exc}"
        )
    logger.info(
        "refinement_proposal: session=%s row=%d resolved intent=%s",
        sid, row_id, result["intent"],
    )
    return result
