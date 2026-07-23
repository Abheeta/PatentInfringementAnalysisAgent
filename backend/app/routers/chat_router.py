from fastapi import APIRouter
from pydantic import BaseModel

from app.services import chat_service

router = APIRouter(tags=["chat"])


class ChatMessageRequest(BaseModel):
    content: str
    row_id: int | None = None


@router.post("/session/{sid}/chat/message")
def send_message(sid: str, body: ChatMessageRequest):
    return chat_service.handle_message(sid, body.content, body.row_id)
