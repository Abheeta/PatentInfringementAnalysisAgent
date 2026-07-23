from fastapi import APIRouter

from app.services import session_service

router = APIRouter(tags=["session"])


@router.post("/session", status_code=201)
def create_session():
    session_id = session_service.create_session()
    return {"session_id": session_id}
