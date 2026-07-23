import io

from docx import Document

from tests.conftest import upload_chart, upload_evidence_text


def test_export_requires_generated(client, sid):
    upload_chart(client, sid)
    r = client.get(f"/session/{sid}/export")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "not_generated_yet"


def test_export_uses_product_feature_not_pending_value(client, sid):
    upload_chart(client, sid)
    upload_evidence_text(client, sid)
    client.post(f"/session/{sid}/generate")

    rows = client.get(f"/session/{sid}/chart").json()["rows"]
    row_id = rows[0]["id"]
    original_feature = rows[0]["product_feature"]

    client.post(
        f"/session/{sid}/chat/message", json={"content": "refine", "row_id": row_id}
    )
    # do NOT accept — pending_value must not appear in the export

    r = client.get(f"/session/{sid}/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    doc = Document(io.BytesIO(r.content))
    table = doc.tables[0]
    body_cells = [row.cells[1].text for row in table.rows[1:]]
    assert original_feature in body_cells
    assert "Dummy proposed evidence value." not in body_cells
