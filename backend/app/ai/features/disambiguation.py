"""Real implementation — ai-design.md §6.1. Call signature unchanged from
the Phase 5 stub.
"""

from app.ai import provider as ai_provider
from app.ai import schemas, validation
from app.ai.baseline_prompt import BASELINE_PROMPT
from app.ai.provider import LLMUnavailableError
from app.ai.validation import StructuredOutputError
from app.services import session_service
from app.services.chart_service import get_rows

_TASK_INSTRUCTION = (
    "Given the chart below and the recent conversation, determine which row "
    "the analyst's latest message refers to. If more than one row is "
    "plausible or none clearly matches, ask a clarifying question instead "
    "of guessing."
)

_RETRY_NOTE = (
    "Your response's needs_clarification value didn't match its row_id/"
    "question fields — if needs_clarification is true, row_id must be null "
    "and question must be non-null; if false, row_id must be non-null and "
    "question must be null."
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
    rows = get_rows(sid)
    if not rows:
        return {
            "row_id": None,
            "needs_clarification": True,
            "question": "Which row are you referring to?",
        }

    system_prompt = session_service.get_system_prompt(sid)
    system_content = BASELINE_PROMPT
    if system_prompt:
        system_content += "\n\n" + system_prompt

    user_content = (
        f"{_TASK_INSTRUCTION}\n\n"
        f"Chart:\n{_format_chart(rows)}\n\n"
        f"Recent conversation:\n{_format_history(history)}\n\n"
        f"Analyst's new message:\n{message}"
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    schema = schemas.disambiguation_schema([r["id"] for r in rows])

    try:
        return validation.call_with_retry(
            ai_provider.get_provider(),
            messages,
            schema,
            validation.validate_disambiguation_pairing,
            _RETRY_NOTE,
        )
    except StructuredOutputError as exc:
        raise LLMUnavailableError(
            f"Model could not produce a usable disambiguation response: {exc}"
        )
