from fastapi import APIRouter

from app.errors import ApiError
from app.services import chart_service, chat_service, evidence_service
from app.services.session_service import get_session

router = APIRouter(tags=["rows"])


@router.post("/session/{sid}/rows/{row_id}/accept", status_code=204)
def accept_row(sid: str, row_id: int):
    get_session(sid)
    chart_service.accept(sid, row_id)


@router.post("/session/{sid}/rows/{row_id}/reject", status_code=204)
def reject_row(sid: str, row_id: int):
    get_session(sid)
    chart_service.reject(sid, row_id)


@router.post("/session/{sid}/rows/{row_id}/undo", status_code=204)
def undo_row(sid: str, row_id: int):
    get_session(sid)
    chart_service.undo(sid, row_id)


@router.post("/session/{sid}/rows/{row_id}/flag")
def flag_row(sid: str, row_id: int):
    get_session(sid)
    chart_service.get_row(sid, row_id)  # raises row_not_found if invalid

    if not evidence_service.has_evidence(sid):
        raise ApiError(
            404,
            "no_evidence_pool",
            "No evidence has been uploaded for this session yet — nothing to re-scan.",
        )

    chart_service.set_flagged(sid, row_id)
    system_note = chat_service.post_flag_system_note(sid, row_id)
    return {"system_note": system_note}
