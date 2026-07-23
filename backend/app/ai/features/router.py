"""Real implementation — ai-design-updated.md §6.1 ("Chat Router", was "Row
Disambiguation"). Call signature: takes sid, message, history — internal to
chat_service, never seen raw by the frontend.
"""

import logging

from app.ai import provider as ai_provider
from app.ai import schemas, validation
from app.ai.baseline_prompt import BASELINE_PROMPT
from app.ai.provider import LLMUnavailableError
from app.ai.validation import StructuredOutputError
from app.services import evidence_service, session_service
from app.services.chart_service import get_rows

logger = logging.getLogger(__name__)

_TASK_INSTRUCTION = (
    "Given the chart, evidence pool, and recent conversation below, decide "
    "how to handle the analyst's latest message. If it asks to review, "
    "refine, or correct a specific row's evidence and you can tell which "
    "row it means, respond with intent `route` and that row's id. If a "
    "specific row seems intended but you can't tell which one, respond "
    "with intent `clarify` and a clarifying question. If it's a general "
    "question you can answer directly and accurately from the chart and "
    "evidence already given below - not a request to change any specific "
    "row - respond with intent `answer` and a grounded answer. Never "
    "guess; if you cannot answer confidently from the given context, "
    "prefer `clarify` or `route` over fabricating an answer.\n\n"
    "Whichever intent you choose, you MUST fill in the one field it "
    "requires - never leave it null or empty:\n"
    "- intent `route`: row_id must be a real row id from the chart above.\n"
    "- intent `clarify`: question must be a real, non-empty clarifying "
    "question written out in full.\n"
    "- intent `answer`: answer must be a real, non-empty answer written out "
    "in full, grounded in the chart and evidence pool above.\n"
    "Leave the other two fields null. The field required by your chosen "
    "intent is what matters most - do not leave that one blank."
)

_RETRY_NOTE = (
    "Your previous response's required field for its chosen intent was "
    "left null/empty. Re-read the rules: intent=route requires a non-null "
    "row_id; intent=clarify requires a real non-empty question written out "
    "in full; intent=answer requires a real non-empty answer written out "
    "in full. Pick one intent and actually write out the text its field "
    "requires - do not leave it null."
)


def _format_chart(rows: list[dict]) -> str:
    lines = [
        f"Row {r['id']}: claim_element={r['claim_element']!r}, "
        f"current_evidence={r['product_feature']!r}"
        for r in rows
    ]
    return "\n".join(lines)


def _format_history(history: list[dict]) -> str:
    lines = [f"{m['role']}: {m['content']}" for m in history]
    return "\n".join(lines)


def resolve_row(sid: str, message: str, history: list[dict]) -> dict:
    logger.info(
        "chat router: session=%s message_chars=%d history_messages=%d",
        sid, len(message), len(history),
    )
    rows = get_rows(sid)
    if not rows:
        return {
            "intent": "clarify",
            "row_id": None,
            "question": "Which row are you referring to?",
            "answer": None,
        }

    evidence_pool = evidence_service.get_evidence_pool(sid)
    logger.info(
        "chat router: session=%s rows=%d evidence_pool_chars=%d",
        sid, len(rows), len(evidence_pool),
    )

    system_prompt = session_service.get_system_prompt(sid)
    system_content = BASELINE_PROMPT
    if system_prompt:
        system_content += "\n\n" + system_prompt

    user_content = (
        f"{_TASK_INSTRUCTION}\n\n"
        f"Chart:\n{_format_chart(rows)}\n\n"
        f"Evidence pool:\n{evidence_pool}\n\n"
        f"Recent conversation:\n{_format_history(history)}\n\n"
        f"Analyst's new message:\n{message}"
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    schema = schemas.router_schema([r["id"] for r in rows])

    try:
        result = validation.call_with_retry(
            ai_provider.get_provider(),
            messages,
            schema,
            validation.validate_router_pairing,
            _RETRY_NOTE,
        )
    except StructuredOutputError as exc:
        raise LLMUnavailableError(
            f"Model could not produce a usable router response: {exc}"
        )
    logger.info("chat router: session=%s resolved intent=%s", sid, result["intent"])
    return result
