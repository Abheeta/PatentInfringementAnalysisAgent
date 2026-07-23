from tests.conftest import upload_chart, upload_evidence_text


def _generate(client, sid):
    upload_chart(client, sid)
    upload_evidence_text(client, sid)
    return client.post(f"/session/{sid}/generate")


def test_generate_requires_chart_uploaded(client, sid):
    r = client.post(f"/session/{sid}/generate")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "chart_not_uploaded"


def test_generate_sets_confidence_and_cannot_repeat(client, sid):
    r = _generate(client, sid)
    assert r.status_code == 200
    assert r.json()["generated"] is True

    rows = client.get(f"/session/{sid}/chart").json()["rows"]
    assert all(row["confidence"] in ("Strong", "Moderate", "Weak") for row in rows)

    r = client.post(f"/session/{sid}/generate")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "already_generated"


def test_chat_requires_generated(client, sid):
    upload_chart(client, sid)
    r = client.post(f"/session/{sid}/chat/message", json={"content": "hello"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "not_generated_yet"


def test_chat_rejects_empty_message(client, sid):
    _generate(client, sid)
    r = client.post(f"/session/{sid}/chat/message", json={"content": "   "})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "empty_message"


def test_chat_rejects_invalid_row_id(client, sid):
    _generate(client, sid)
    r = client.post(
        f"/session/{sid}/chat/message", json={"content": "hi", "row_id": 9999}
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "row_not_found"


def test_accept_reject_undo_cycle(client, sid):
    _generate(client, sid)
    rows = client.get(f"/session/{sid}/chart").json()["rows"]
    row_id = rows[0]["id"]
    original_feature = rows[0]["product_feature"]

    r = client.post(f"/session/{sid}/rows/{row_id}/accept")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_pending_proposal"

    r = client.post(f"/session/{sid}/rows/{row_id}/reject")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_pending_proposal"

    client.post(
        f"/session/{sid}/chat/message", json={"content": "refine", "row_id": row_id}
    )

    r = client.post(f"/session/{sid}/rows/{row_id}/undo")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_undo_available"

    r = client.post(f"/session/{sid}/rows/{row_id}/accept")
    assert r.status_code == 204

    row = next(
        r for r in client.get(f"/session/{sid}/chart").json()["rows"]
        if r["id"] == row_id
    )
    assert row["pending_value"] is None
    assert row["previous_product_feature"] == original_feature
    assert row["product_feature"] != original_feature

    r = client.post(f"/session/{sid}/rows/{row_id}/undo")
    assert r.status_code == 204

    row = next(
        r for r in client.get(f"/session/{sid}/chart").json()["rows"]
        if r["id"] == row_id
    )
    assert row["product_feature"] == original_feature
    assert row["previous_product_feature"] is None


def test_reject_clears_pending_without_changing_live_values(client, sid):
    _generate(client, sid)
    rows = client.get(f"/session/{sid}/chart").json()["rows"]
    row_id = rows[0]["id"]
    original_feature = rows[0]["product_feature"]

    client.post(
        f"/session/{sid}/chat/message", json={"content": "refine", "row_id": row_id}
    )
    r = client.post(f"/session/{sid}/rows/{row_id}/reject")
    assert r.status_code == 204

    row = next(
        r for r in client.get(f"/session/{sid}/chart").json()["rows"]
        if r["id"] == row_id
    )
    assert row["pending_value"] is None
    assert row["product_feature"] == original_feature


def test_flag_requires_evidence_pool(client, sid):
    upload_chart(client, sid)
    row_id = client.get(f"/session/{sid}/chart").json()["rows"][0]["id"]
    r = client.post(f"/session/{sid}/rows/{row_id}/flag")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "no_evidence_pool"


def test_flag_then_reflag_conflict_and_clears_after_message(client, sid):
    _generate(client, sid)
    row_id = client.get(f"/session/{sid}/chart").json()["rows"][0]["id"]

    r = client.post(f"/session/{sid}/rows/{row_id}/flag")
    assert r.status_code == 200
    assert r.json()["system_note"]["row_id"] == row_id

    r = client.post(f"/session/{sid}/rows/{row_id}/flag")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "already_flagged"

    client.post(
        f"/session/{sid}/chat/message",
        json={"content": "this is wrong", "row_id": row_id},
    )

    row = next(
        r for r in client.get(f"/session/{sid}/chart").json()["rows"]
        if r["id"] == row_id
    )
    assert row["flagged"] is False


def test_flag_blocks_flagging_other_row_until_resolved(client, sid):
    _generate(client, sid)
    rows = client.get(f"/session/{sid}/chart").json()["rows"]
    row_id_1 = rows[0]["id"]
    row_id_2 = rows[1]["id"]

    r = client.post(f"/session/{sid}/rows/{row_id_1}/flag")
    assert r.status_code == 200

    r = client.post(f"/session/{sid}/rows/{row_id_2}/flag")
    assert r.status_code == 409
    body = r.json()["error"]
    assert body["code"] == "already_flagged"
    assert str(row_id_1) in body["message"]

    client.post(
        f"/session/{sid}/chat/message",
        json={"content": "this is wrong", "row_id": row_id_1},
    )

    r = client.post(f"/session/{sid}/rows/{row_id_2}/flag")
    assert r.status_code == 200
