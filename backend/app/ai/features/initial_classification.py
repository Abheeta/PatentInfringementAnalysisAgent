"""Real implementation — ai-design.md §6.3. Call signature unchanged from
the Phase 5 stub.
"""

from app.ai import provider as ai_provider
from app.ai import schemas, validation
from app.ai.baseline_prompt import BASELINE_PROMPT
from app.ai.provider import LLMUnavailableError
from app.ai.validation import StructuredOutputError
from app.services import evidence_service, session_service
from app.services.chart_service import get_rows

_RUBRIC = (
    "Strong = evidence directly states the claim element; Moderate = "
    "evidence implies it, requires inference; Weak = evidence is "
    "tangential or absent."
)

_TASK_INSTRUCTION = (
    "Classify the confidence tier for every row below, based on evidence "
    "directness. Do not rewrite the evidence or reasoning text — "
    "classification only. For each row, also give a short `reasoning` "
    "explaining the confidence tier: for Strong, a brief one-line "
    "justification is enough; for Moderate or Weak, explain what's missing "
    "or merely implied so the analyst knows what to go check."
)

_RETRY_NOTE = (
    "Your response didn't include exactly one classification per row in "
    "this chart — return one entry per row id, no duplicates, none "
    "missing."
)


def _format_chart(rows: list[dict]) -> str:
    lines = [
        f"Row {r['id']}: claim_element={r['claim_element']!r}, "
        f"evidence={r['product_feature']!r}, reasoning={r['ai_reasoning']!r}"
        for r in rows
    ]
    return "\n".join(lines)


def classify_all(sid: str) -> list[dict]:
    rows = get_rows(sid)
    evidence_pool = evidence_service.get_evidence_pool(sid)

    system_prompt = session_service.get_system_prompt(sid)
    system_content = f"{BASELINE_PROMPT}\n\n{_RUBRIC}"
    if system_prompt:
        system_content += "\n\n" + system_prompt

    user_content = (
        f"{_TASK_INSTRUCTION}\n\n"
        f"Chart:\n{_format_chart(rows)}\n\n"
        f"Evidence pool:\n{evidence_pool}"
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    row_ids = [r["id"] for r in rows]
    schema = schemas.classification_schema(row_ids)

    try:
        result = validation.call_with_retry(
            ai_provider.get_provider(),
            messages,
            schema,
            validation.validate_classification_rowset(row_ids),
            _RETRY_NOTE,
        )
    except StructuredOutputError as exc:
        raise LLMUnavailableError(
            f"Model could not produce a valid classification for every row: {exc}"
        )

    return result["classifications"]
