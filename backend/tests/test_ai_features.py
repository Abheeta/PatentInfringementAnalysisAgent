import pytest

from app.ai import provider as ai_provider
from app.ai.provider import LLMUnavailableError
from app.ai.features import (
    initial_classification,
    refinement_proposal,
    regrounded_correction,
    router,
)
from tests.conftest import upload_chart, upload_evidence_text
from tests.fakes import FakeProvider


def _setup(client, sid):
    upload_chart(client, sid)
    upload_evidence_text(client, sid)


def _fake(monkeypatch, *responses):
    fake = FakeProvider(list(responses))
    monkeypatch.setattr(ai_provider, "get_provider", lambda: fake)
    return fake


def _row_ids(client, sid):
    return [r["id"] for r in client.get(f"/session/{sid}/chart").json()["rows"]]


# --- initial_classification ---------------------------------------------


def test_classify_all_happy_path(client, sid, monkeypatch):
    _setup(client, sid)
    ids = _row_ids(client, sid)
    _fake(
        monkeypatch,
        {
            "classifications": [
                {"row_id": rid, "confidence": "Strong", "reasoning": "r"}
                for rid in ids
            ]
        },
    )
    result = initial_classification.classify_all(sid)
    assert {c["row_id"] for c in result} == set(ids)


def test_classify_all_retries_then_succeeds(client, sid, monkeypatch):
    _setup(client, sid)
    ids = _row_ids(client, sid)
    valid = {
        "classifications": [
            {"row_id": rid, "confidence": "Strong", "reasoning": "r"} for rid in ids
        ]
    }
    invalid = {"classifications": [{"row_id": ids[0], "confidence": "Strong", "reasoning": "r"}]}
    fake = _fake(monkeypatch, invalid, valid)
    result = initial_classification.classify_all(sid)
    assert {c["row_id"] for c in result} == set(ids)
    assert len(fake.calls) == 2


def test_classify_all_fails_twice_raises_unavailable(client, sid, monkeypatch):
    _setup(client, sid)
    ids = _row_ids(client, sid)
    invalid = {"classifications": [{"row_id": ids[0], "confidence": "Strong", "reasoning": "r"}]}
    _fake(monkeypatch, invalid, invalid)
    with pytest.raises(LLMUnavailableError):
        initial_classification.classify_all(sid)


# --- chat router -----------------------------------------------------------


def test_router_routes_to_a_row(client, sid, monkeypatch):
    _setup(client, sid)
    ids = _row_ids(client, sid)
    _fake(
        monkeypatch,
        {"intent": "route", "row_id": ids[0], "question": None, "answer": None},
    )
    result = router.resolve_row(sid, "what about the processor", [])
    assert result["intent"] == "route"
    assert result["row_id"] == ids[0]


def test_router_asks_clarification(client, sid, monkeypatch):
    _setup(client, sid)
    _fake(
        monkeypatch,
        {"intent": "clarify", "row_id": None, "question": "Which row?", "answer": None},
    )
    result = router.resolve_row(sid, "what about that", [])
    assert result["intent"] == "clarify"
    assert result["question"] == "Which row?"


def test_router_answers_general_question(client, sid, monkeypatch):
    _setup(client, sid)
    _fake(
        monkeypatch,
        {
            "intent": "answer",
            "row_id": None,
            "question": None,
            "answer": "The chart has 3 rows, all currently Strong.",
        },
    )
    result = router.resolve_row(sid, "how many rows are there", [])
    assert result["intent"] == "answer"
    assert result["answer"] == "The chart has 3 rows, all currently Strong."


def test_router_bad_pairing_retries_then_fails(client, sid, monkeypatch):
    _setup(client, sid)
    ids = _row_ids(client, sid)
    bad = {"intent": "clarify", "row_id": ids[0], "question": None, "answer": None}
    _fake(monkeypatch, bad, bad)
    with pytest.raises(LLMUnavailableError):
        router.resolve_row(sid, "hmm", [])


# --- refinement_proposal (row turn) ----------------------------------------


def test_row_turn_propose_happy_path(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    _fake(
        monkeypatch,
        {
            "row_id": row_id,
            "intent": "propose",
            "answer": None,
            "no_evidence_found": False,
            "proposed_value": "Snapdragon processor",
            "reasoning": "Directly stated.",
            "confidence": "Strong",
        },
    )
    result = refinement_proposal.propose(sid, row_id, "make it stronger")
    assert result["intent"] == "propose"
    assert result["proposed_value"] == "Snapdragon processor"


def test_row_turn_answers_question_about_row(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    _fake(
        monkeypatch,
        {
            "row_id": row_id,
            "intent": "answer",
            "answer": "The current evidence cites the spec sheet directly.",
            "no_evidence_found": None,
            "proposed_value": None,
            "reasoning": None,
            "confidence": None,
        },
    )
    result = refinement_proposal.propose(sid, row_id, "why is this strong?")
    assert result["intent"] == "answer"
    assert result["answer"] == "The current evidence cites the spec sheet directly."


def test_row_turn_bad_pairing_retries_then_fails(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    bad = {
        "row_id": row_id,
        "intent": "propose",
        "answer": None,
        "no_evidence_found": False,
        "proposed_value": None,
        "reasoning": None,
        "confidence": None,
    }
    _fake(monkeypatch, bad, bad)
    with pytest.raises(LLMUnavailableError):
        refinement_proposal.propose(sid, row_id, "make it stronger")


def test_row_turn_answer_with_stray_propose_fields_still_accepted(client, sid, monkeypatch):
    """A relaxed-validation regression case: the model picks intent=answer
    but also fills in propose-shaped fields instead of leaving them null.
    Since chat_service never reads those fields for the `answer` path, this
    should be accepted rather than treated as a structured-output failure.
    """
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    _fake(
        monkeypatch,
        {
            "row_id": row_id,
            "intent": "answer",
            "answer": "The evidence cites the spec sheet directly.",
            "no_evidence_found": False,
            "proposed_value": "some stray value",
            "reasoning": "some stray reasoning",
            "confidence": "Strong",
        },
    )
    result = refinement_proposal.propose(sid, row_id, "what does the evidence say?")
    assert result["intent"] == "answer"
    assert result["answer"] == "The evidence cites the spec sheet directly."


# --- regrounded_correction -------------------------------------------------


def test_correction_valid_verbatim_quote(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    _fake(
        monkeypatch,
        {
            "row_id": row_id,
            "intent": "propose",
            "answer": None,
            "no_evidence_found": False,
            "proposed_value": "The device includes a Snapdragon processor.",
            "reasoning": "Verbatim match.",
            "confidence": "Strong",
        },
    )
    result = regrounded_correction.correct(sid, row_id, "this looks wrong")
    assert result["intent"] == "propose"
    assert result["no_evidence_found"] is False


def test_correction_answers_question_without_resolving_flag(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    _fake(
        monkeypatch,
        {
            "row_id": row_id,
            "intent": "answer",
            "answer": "It was flagged because the evidence looked tangential.",
            "no_evidence_found": None,
            "proposed_value": None,
            "reasoning": None,
            "confidence": None,
        },
    )
    result = regrounded_correction.correct(sid, row_id, "why was this flagged?")
    assert result["intent"] == "answer"
    assert result["answer"] == "It was flagged because the evidence looked tangential."


def test_correction_paraphrase_retries_then_converges_no_evidence(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    paraphrase = {
        "row_id": row_id,
        "intent": "propose",
        "answer": None,
        "no_evidence_found": False,
        "proposed_value": "It has a Snapdragon chip inside.",
        "reasoning": "Paraphrased.",
        "confidence": "Strong",
    }
    fake = _fake(monkeypatch, paraphrase, paraphrase)
    result = regrounded_correction.correct(sid, row_id, "this looks wrong")
    assert result["intent"] == "propose"
    assert result["no_evidence_found"] is True
    assert len(fake.calls) == 2


def test_correction_retries_then_succeeds_with_real_verbatim_quote(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    paraphrase = {
        "row_id": row_id,
        "intent": "propose",
        "answer": None,
        "no_evidence_found": False,
        "proposed_value": "It has a Snapdragon chip inside.",
        "reasoning": "Paraphrased.",
        "confidence": "Strong",
    }
    verbatim = {
        "row_id": row_id,
        "intent": "propose",
        "answer": None,
        "no_evidence_found": False,
        "proposed_value": "The device includes a Snapdragon processor.",
        "reasoning": "Verbatim match.",
        "confidence": "Strong",
    }
    _fake(monkeypatch, paraphrase, verbatim)
    result = regrounded_correction.correct(sid, row_id, "this looks wrong")
    assert result["intent"] == "propose"
    assert result["no_evidence_found"] is False
    assert result["proposed_value"] == "The device includes a Snapdragon processor."


def test_correction_bad_answer_pairing_retries_then_raises(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    bad = {
        "row_id": row_id,
        "intent": "answer",
        "answer": None,
        "no_evidence_found": None,
        "proposed_value": None,
        "reasoning": None,
        "confidence": None,
    }
    _fake(monkeypatch, bad, bad)
    with pytest.raises(LLMUnavailableError):
        regrounded_correction.correct(sid, row_id, "why was this flagged?")
