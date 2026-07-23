import os
import uuid

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_path = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))

    # app.config.settings is a module-level singleton read at import time;
    # re-point it at the per-test db so each test gets an isolated schema.
    from app.config import settings

    settings.SQLITE_PATH = str(db_path)

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def sid(client):
    r = client.post("/session")
    return r.json()["session_id"]


CHART_CSV = (
    "Claim Element,Evidence,Reasoning\n"
    "a processor configured to receive a signal,Snapdragon processor,Spec sheet describes reception\n"
    "a memory storing instructions,No mention found,No evidence located\n"
    "a display unit,OLED display present,Spec sheet lists OLED display\n"
)


def upload_chart(client, sid, csv_text=CHART_CSV):
    files = {"file": ("chart.csv", csv_text, "text/csv")}
    return client.post(f"/session/{sid}/upload-chart", files=files)


def upload_evidence_text(client, sid, text="The device includes a Snapdragon processor."):
    files = {"file": ("evidence.txt", text, "text/plain")}
    return client.post(f"/session/{sid}/upload-evidence", files=files)
