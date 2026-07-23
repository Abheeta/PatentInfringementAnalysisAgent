"""Stub implementation. Real version (Phase 14) will call LLMProvider with
the classification_schema and validate the full-row-set match — see
ai-design.md §6.3. Call signature must not change when that happens.
"""

from app.services.chart_service import get_rows

_TIER_CYCLE = ["Strong", "Moderate", "Weak"]


def classify_all(sid: str) -> list[dict]:
    rows = get_rows(sid)
    return [
        {
            "row_id": row["id"],
            "confidence": _TIER_CYCLE[i % len(_TIER_CYCLE)],
            "reasoning": "Dummy classification reasoning.",
        }
        for i, row in enumerate(rows)
    ]
