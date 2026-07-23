import httpx
from bs4 import BeautifulSoup

from app.db.connection import get_connection
from app.errors import ApiError
from app.services.session_service import get_session

_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def store_uploaded_text(sid: str, filename: str, text: str) -> None:
    conn = get_connection()
    try:
        get_session(sid, conn)
        conn.execute(
            """INSERT INTO evidence_docs (session_id, source_type, source_label, content)
               VALUES (?, 'upload', ?, ?)""",
            (sid, filename, text),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_url(sid: str, url: str) -> None:
    conn = get_connection()
    try:
        get_session(sid, conn)
    finally:
        conn.close()

    try:
        response = httpx.get(
            url, timeout=10, follow_redirects=True, headers=_FETCH_HEADERS
        )
    except httpx.TimeoutException:
        raise ApiError(
            400,
            "url_fetch_failed",
            "Couldn't fetch that URL: request timed out after 10s.",
        )
    except httpx.HTTPError as exc:
        raise ApiError(
            400, "url_fetch_failed", f"Couldn't fetch that URL: {exc}."
        )

    if response.status_code != 200:
        raise ApiError(
            400,
            "url_fetch_failed",
            f"Couldn't fetch that URL: server returned status {response.status_code}.",
        )

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower():
        raise ApiError(
            400,
            "url_fetch_failed",
            f"Couldn't fetch that URL: unsupported content type '{content_type}'.",
        )

    text = BeautifulSoup(response.text, "html.parser").get_text()
    text = " ".join(text.split())

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO evidence_docs (session_id, source_type, source_label, content)
               VALUES (?, 'url', ?, ?)""",
            (sid, url, text),
        )
        conn.commit()
    finally:
        conn.close()


def get_evidence_pool(sid: str) -> str:
    conn = get_connection()
    try:
        docs = conn.execute(
            "SELECT source_label, content FROM evidence_docs WHERE session_id = ?",
            (sid,),
        ).fetchall()
        return "\n\n".join(f"[{d['source_label']}]\n{d['content']}" for d in docs)
    finally:
        conn.close()


def has_evidence(sid: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM evidence_docs WHERE session_id = ?", (sid,)
        ).fetchone()
        return row["c"] > 0
    finally:
        conn.close()
