from fastapi import APIRouter
from pydantic import BaseModel

from app.services import session_service

router = APIRouter(tags=["system-prompt"])


class SystemPromptRequest(BaseModel):
    system_prompt: str


@router.get("/session/{sid}/system-prompt")
def get_system_prompt(sid: str):
    return {"system_prompt": session_service.get_system_prompt(sid)}


@router.put("/session/{sid}/system-prompt", status_code=204)
def put_system_prompt(sid: str, body: SystemPromptRequest):
    session_service.set_system_prompt(sid, body.system_prompt)
