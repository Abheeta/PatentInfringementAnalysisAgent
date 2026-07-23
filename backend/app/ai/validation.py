"""Retry-once-then-error orchestration + per-feature validation rules, per
ai-design.md §4 and each call's "Validation beyond the schema" in §6.
"""

from typing import Callable

from app.ai.provider import LLMProvider


class StructuredOutputError(Exception):
    """Raised when a response fails validation twice in a row."""


def call_with_retry(
    provider: LLMProvider,
    messages: list[dict],
    schema: dict,
    validate_fn: Callable[[dict], None],
    retry_note: str,
) -> dict:
    result = provider.generate(messages, schema)
    try:
        validate_fn(result)
        return result
    except ValueError:
        pass

    retry_messages = messages + [{"role": "user", "content": retry_note}]
    result = provider.generate(retry_messages, schema)
    try:
        validate_fn(result)
        return result
    except ValueError as exc:
        raise StructuredOutputError(str(exc))


def validate_disambiguation_pairing(result: dict) -> None:
    if result["needs_clarification"]:
        if result["row_id"] is not None or not result["question"]:
            raise ValueError(
                "needs_clarification=true requires row_id=null and a non-null question."
            )
    else:
        if result["row_id"] is None or result["question"] is not None:
            raise ValueError(
                "needs_clarification=false requires a non-null row_id and question=null."
            )


def validate_proposal_pairing(result: dict) -> None:
    if result["no_evidence_found"]:
        if (
            result["proposed_value"] is not None
            or result["reasoning"] is not None
            or result["confidence"] is not None
        ):
            raise ValueError(
                "no_evidence_found=true requires proposed_value, reasoning, "
                "and confidence to all be null."
            )
    else:
        if result["proposed_value"] is None or result["reasoning"] is None:
            raise ValueError(
                "no_evidence_found=false requires non-null proposed_value and reasoning."
            )


def validate_classification_rowset(expected_row_ids: list[int]) -> Callable[[dict], None]:
    expected = set(expected_row_ids)

    def _validate(result: dict) -> None:
        got = {item["row_id"] for item in result["classifications"]}
        if got != expected or len(result["classifications"]) != len(expected):
            raise ValueError(
                f"Expected classifications for exactly row ids {sorted(expected)}, "
                f"got {sorted(got)}."
            )

    return _validate


def validate_verbatim_quote(evidence_pool: str) -> Callable[[dict], None]:
    def _validate(result: dict) -> None:
        validate_proposal_pairing(result)
        if not result["no_evidence_found"] and result["proposed_value"] not in evidence_pool:
            raise ValueError("proposed_value was not found verbatim in the evidence pool.")

    return _validate
