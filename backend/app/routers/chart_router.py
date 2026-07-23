from fastapi import APIRouter

from app.ai.features import initial_classification, opening_message
from app.db.connection import get_connection
from app.errors import ApiError
from app.services import chart_service
from app.services.session_service import get_session

router = APIRouter(tags=["chart"])


@router.get("/session/{sid}/chart")
def get_chart(sid: str):
    rows = chart_service.get_rows(sid)
    return {"rows": rows}


@router.post("/session/{sid}/generate")
def generate(sid: str):
    conn = get_connection()
    try:
        session = get_session(sid, conn)
        if not session["chart_uploaded"]:
            raise ApiError(
                400, "chart_not_uploaded", "Upload a chart before generating."
            )
        if session["generated"]:
            raise ApiError(
                409,
                "already_generated",
                "This session has already been generated.",
            )
    finally:
        conn.close()

    classifications = initial_classification.classify_all(sid)
    chart_service.apply_classifications(sid, classifications)

    rows = chart_service.get_rows(sid)
    content = opening_message.compose_opening_message(rows)
    message = chart_service.finalize_generate(sid, content)

    return {"generated": True, "opening_message": message}
