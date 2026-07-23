"""Stub implementation. Real version (Phase 14) will call LLMProvider with
the proposal_schema plus the verbatim-quote validation — see ai-design.md
§6.5. Call signature must not change when that happens.
"""


def correct(sid: str, row_id: int, message: str) -> dict:
    return {
        "row_id": row_id,
        "no_evidence_found": False,
        "proposed_value": "Dummy verbatim-looking quote from the evidence pool.",
        "reasoning": "Dummy re-grounded correction reasoning.",
        "confidence": "Strong",
    }
