"""Stub implementation. Real version (Phase 14) will call LLMProvider with
the proposal_schema, grounded in the evidence pool — see ai-design.md §6.2.
Call signature must not change when that happens.
"""


def propose(sid: str, row_id: int, message: str) -> dict:
    return {
        "row_id": row_id,
        "no_evidence_found": False,
        "proposed_value": "Dummy proposed evidence value.",
        "reasoning": "Dummy reasoning for the proposed value.",
        "confidence": "Moderate",
    }
