import pytest

from app.ai import provider as ai_provider
from app.ai.provider import LLMUnavailableError
from app.ai.features import (
    disambiguation,
    initial_classification,
    refinement_proposal,
    regrounded_correction,
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


# --- disambiguation -------------------------------------------------------


def test_disambiguation_resolves(client, sid, monkeypatch):
    _setup(client, sid)
    ids = _row_ids(client, sid)
    _fake(
        monkeypatch,
        {"row_id": ids[0], "needs_clarification": False, "question": None},
    )
    result = disambiguation.resolve_row(sid, "what about the processor", [])
    assert result["row_id"] == ids[0]
    assert result["needs_clarification"] is False


def test_disambiguation_asks_clarification(client, sid, monkeypatch):
    _setup(client, sid)
    _fake(
        monkeypatch,
        {"row_id": None, "needs_clarification": True, "question": "Which row?"},
    )
    result = disambiguation.resolve_row(sid, "what about that", [])
    assert result["needs_clarification"] is True
    assert result["question"] == "Which row?"


def test_disambiguation_bad_pairing_retries_then_fails(client, sid, monkeypatch):
    _setup(client, sid)
    ids = _row_ids(client, sid)
    bad = {"row_id": ids[0], "needs_clarification": True, "question": None}
    _fake(monkeypatch, bad, bad)
    with pytest.raises(LLMUnavailableError):
        disambiguation.resolve_row(sid, "hmm", [])


# --- refinement_proposal --------------------------------------------------


def test_proposal_happy_path(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    _fake(
        monkeypatch,
        {
            "row_id": row_id,
            "no_evidence_found": False,
            "proposed_value": "Snapdragon processor",
            "reasoning": "Directly stated.",
            "confidence": "Strong",
        },
    )
    result = refinement_proposal.propose(sid, row_id, "make it stronger")
    assert result["proposed_value"] == "Snapdragon processor"


def test_proposal_bad_pairing_retries_then_fails(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    bad = {
        "row_id": row_id,
        "no_evidence_found": True,
        "proposed_value": "should be null",
        "reasoning": None,
        "confidence": None,
    }
    _fake(monkeypatch, bad, bad)
    with pytest.raises(LLMUnavailableError):
        refinement_proposal.propose(sid, row_id, "make it stronger")


# --- regrounded_correction -------------------------------------------------


def test_correction_valid_verbatim_quote(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    _fake(
        monkeypatch,
        {
            "row_id": row_id,
            "no_evidence_found": False,
            "proposed_value": "The device includes a Snapdragon processor.",
            "reasoning": "Verbatim match.",
            "confidence": "Strong",
        },
    )
    result = regrounded_correction.correct(sid, row_id, "this looks wrong")
    assert result["no_evidence_found"] is False


def test_correction_paraphrase_retries_then_converges_no_evidence(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    paraphrase = {
        "row_id": row_id,
        "no_evidence_found": False,
        "proposed_value": "It has a Snapdragon chip inside.",
        "reasoning": "Paraphrased.",
        "confidence": "Strong",
    }
    fake = _fake(monkeypatch, paraphrase, paraphrase)
    result = regrounded_correction.correct(sid, row_id, "this looks wrong")
    assert result["no_evidence_found"] is True
    assert len(fake.calls) == 2


def test_correction_retries_then_succeeds_with_real_verbatim_quote(client, sid, monkeypatch):
    _setup(client, sid)
    row_id = _row_ids(client, sid)[0]
    paraphrase = {
        "row_id": row_id,
        "no_evidence_found": False,
        "proposed_value": "It has a Snapdragon chip inside.",
        "reasoning": "Paraphrased.",
        "confidence": "Strong",
    }
    verbatim = {
        "row_id": row_id,
        "no_evidence_found": False,
        "proposed_value": "The device includes a Snapdragon processor.",
        "reasoning": "Verbatim match.",
        "confidence": "Strong",
    }
    _fake(monkeypatch, paraphrase, verbatim)
    result = regrounded_correction.correct(sid, row_id, "this looks wrong")
    assert result["no_evidence_found"] is False
    assert result["proposed_value"] == "The device includes a Snapdragon processor."
