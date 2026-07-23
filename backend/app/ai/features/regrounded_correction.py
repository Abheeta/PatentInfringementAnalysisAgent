"""Real implementation — ai-design.md §6.5. Call signature unchanged from
the Phase 5 stub. Reuses §6.2's shape, with a verbatim-quote requirement
and a converge-to-no_evidence_found fallback on a second failure (instead
of erroring, per §6.5).
"""

from app.ai import provider as ai_provider
from app.ai import schemas, validation
from app.ai.baseline_prompt import BASELINE_PROMPT
from app.ai.validation import StructuredOutputError
from app.db.connection import get_connection
from app.services import evidence_service, session_service
from app.services.chart_service import get_row

_TASK_INSTRUCTION = (
    "Given this row's claim element, its current evidence and reasoning, "
    "the full evidence pool, and this row's own conversation history, the "
    "analyst has flagged this row's evidence as potentially wrong. Find and "
    "quote the relevant line verbatim from the evidence pool — do not "
    "paraphrase. If no supporting line exists anywhere in the pool, state "
    "that no evidence was found."
)

_RETRY_NOTE = (
    "Your last answer wasn't found verbatim in the source text — quote the "
    "exact line from the evidence pool, do not paraphrase. If no such line "
    "exists, set no_evidence_found to true instead."
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
    row = get_row(sid, row_id)
    evidence_pool = evidence_service.get_evidence_pool(sid)
    thread = _row_thread(sid, row_id)

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
    schema = schemas.proposal_schema(row_id)

    try:
        return validation.call_with_retry(
            ai_provider.get_provider(),
            messages,
            schema,
            validation.validate_verbatim_quote(evidence_pool),
            _RETRY_NOTE,
        )
    except StructuredOutputError:
        return {
            "row_id": row_id,
            "no_evidence_found": True,
            "proposed_value": None,
            "reasoning": None,
            "confidence": None,
        }
