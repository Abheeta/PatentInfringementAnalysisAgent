import httpx
import pytest

from app.errors import ApiError
from app.services import evidence_service
from tests.conftest import upload_chart


class _FakeResponse:
    def __init__(self, status_code, content_type, text):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.text = text


def test_fetch_url_succeeds_without_chart_uploaded(monkeypatch, sid):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: _FakeResponse(
            200, "text/html", "<html><body>Signal reception module</body></html>"
        ),
    )
    evidence_service.fetch_url(sid, "http://example.com")
    pool = evidence_service.get_evidence_pool(sid)
    assert "Signal reception module" in pool


def test_fetch_url_non_200(monkeypatch, client, sid):
    upload_chart(client, sid)
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _FakeResponse(404, "text/html", "not found")
    )
    with pytest.raises(ApiError) as excinfo:
        evidence_service.fetch_url(sid, "http://example.com")
    assert excinfo.value.code == "url_fetch_failed"
    assert "404" in excinfo.value.message


def test_fetch_url_timeout(monkeypatch, client, sid):
    upload_chart(client, sid)

    def raise_timeout(*a, **k):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "get", raise_timeout)
    with pytest.raises(ApiError) as excinfo:
        evidence_service.fetch_url(sid, "http://example.com")
    assert excinfo.value.code == "url_fetch_failed"
    assert "timed out" in excinfo.value.message


def test_fetch_url_non_html_content_type(monkeypatch, client, sid):
    upload_chart(client, sid)
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: _FakeResponse(200, "application/pdf", "%PDF-1.4"),
    )
    with pytest.raises(ApiError) as excinfo:
        evidence_service.fetch_url(sid, "http://example.com")
    assert excinfo.value.code == "url_fetch_failed"


def test_fetch_url_success_stores_evidence_doc(monkeypatch, client, sid):
    upload_chart(client, sid)
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: _FakeResponse(
            200, "text/html", "<html><body>Signal reception module</body></html>"
        ),
    )
    evidence_service.fetch_url(sid, "http://example.com")
    pool = evidence_service.get_evidence_pool(sid)
    assert "Signal reception module" in pool
