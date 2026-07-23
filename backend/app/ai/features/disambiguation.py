"""Stub implementation. Real version (Phase 14) will call LLMProvider with
the disambiguation_schema built from this session's row ids — see
ai-design.md §6.1. Call signature must not change when that happens.
"""

from app.services.chart_service import get_rows


def resolve_row(sid: str, message: str, history: list[dict]) -> dict:
    rows = get_rows(sid)
    if not rows:
        return {
            "row_id": None,
            "needs_clarification": True,
            "question": "Which row are you referring to?",
        }
    return {
        "row_id": rows[0]["id"],
        "needs_clarification": False,
        "question": None,
    }
