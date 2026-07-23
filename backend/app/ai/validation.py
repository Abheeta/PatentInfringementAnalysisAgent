"""Retry-once-then-error orchestration + per-feature validation rules, per
ai-design-updated.md §4 and each call's "Validation beyond the schema" in §6.
"""

from typing import Callable

from app.ai.provider import LLMProvider


class StructuredOutputError(Exception):
    """Raised when a response fails validation twice in a row.

    `last_result` carries the second (still-invalid) response so callers with
    a fallback path (e.g. §6.5's converge-to-no_evidence_found) can inspect
    what the model actually returned, rather than only the error string.
    """

    def __init__(self, message: str, last_result: dict | None = None):
        super().__init__(message)
        self.last_result = last_result


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
        raise StructuredOutputError(str(exc), last_result=result)


def validate_router_pairing(result: dict) -> None:
    """Only checks the field(s) the chosen intent actually needs.

    Fields belonging to the *other* intents are ignored even if the model
    also filled them in — chat_service only ever reads the field(s) for the
    resolved intent, so a stray non-null value elsewhere is never acted on.
    Relaxed from a stricter "everything else must be null" rule after that
    stricter rule proved unreliable against the small local model, which
    tends to fill in every field it can rather than leaving unused ones
    empty (see chat conversation for the reproduction).
    """
    intent = result["intent"]
    if intent == "route":
        if result["row_id"] is None:
            raise ValueError("intent=route requires a non-null row_id.")
    elif intent == "clarify":
        if not result["question"]:
            raise ValueError("intent=clarify requires a non-null question.")
    elif intent == "answer":
        if not result["answer"]:
            raise ValueError("intent=answer requires a non-null answer.")
    else:
        raise ValueError(f"Unrecognized intent: {intent!r}")


def validate_row_turn_pairing(result: dict) -> None:
    """Only checks the field(s) the chosen intent actually needs — see
    validate_router_pairing's docstring for why the stricter "everything
    else must be null" rule was relaxed.
    """
    intent = result["intent"]
    if intent == "answer":
        if not result["answer"]:
            raise ValueError("intent=answer requires a non-null answer.")
    elif intent == "propose":
        if result["no_evidence_found"] is None:
            raise ValueError("intent=propose requires a non-null no_evidence_found.")
        if not result["no_evidence_found"]:
            if result["proposed_value"] is None or result["reasoning"] is None:
                raise ValueError(
                    "no_evidence_found=false requires non-null proposed_value and reasoning."
                )
    else:
        raise ValueError(f"Unrecognized intent: {intent!r}")


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
        validate_row_turn_pairing(result)
        if (
            result["intent"] == "propose"
            and not result["no_evidence_found"]
            and result["proposed_value"] not in evidence_pool
        ):
            raise ValueError("proposed_value was not found verbatim in the evidence pool.")

    return _validate
