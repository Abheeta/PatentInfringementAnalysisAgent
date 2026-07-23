from tests.conftest import upload_chart


def test_upload_chart_success(client, sid):
    r = upload_chart(client, sid)
    assert r.status_code == 204

    r = client.get(f"/session/{sid}/chart")
    rows = r.json()["rows"]
    assert len(rows) == 3
    assert rows[0]["claim_element"] == "a processor configured to receive a signal"
    assert rows[0]["confidence"] is None


def test_header_row_always_skipped_regardless_of_wording(client, sid):
    csv_text = (
        "whatever,header,text\n"
        "elem1,evidence1,reason1\n"
    )
    r = upload_chart(client, sid, csv_text)
    assert r.status_code == 204
    rows = client.get(f"/session/{sid}/chart").json()["rows"]
    assert len(rows) == 1
    assert rows[0]["claim_element"] == "elem1"


def test_malformed_csv_wrong_column_count(client, sid):
    csv_text = (
        "header1,header2,header3\n"
        "elem1,evidence1\n"  # only 2 columns
    )
    r = upload_chart(client, sid, csv_text)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "malformed_csv"


def test_invalid_file_type_rejected(client, sid):
    files = {"file": ("chart.txt", "a,b,c\n1,2,3\n", "text/plain")}
    r = client.post(f"/session/{sid}/upload-chart", files=files)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_file_type"


def test_file_too_large_rejected(client, sid):
    huge_row = "x" * (5 * 1024 * 1024 + 1)
    csv_text = f"header\n{huge_row},b,c\n"
    files = {"file": ("chart.csv", csv_text, "text/csv")}
    r = client.post(f"/session/{sid}/upload-chart", files=files)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "file_too_large"


def test_chart_already_exists_on_second_upload(client, sid):
    upload_chart(client, sid)
    r = upload_chart(client, sid)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "chart_already_exists"


def test_bom_prefixed_csv_decodes_successfully(client, sid):
    csv_text = "﻿header1,header2,header3\nelem1,evidence1,reason1\n"
    r = upload_chart(client, sid, csv_text)
    assert r.status_code == 204
