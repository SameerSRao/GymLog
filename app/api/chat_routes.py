import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_routes import get_current_user, require_not_demo
from app.db.database import get_db
from app.services.chat_service import run_chat

router = APIRouter(dependencies=[Depends(get_current_user)])


class ChatMessage(BaseModel):
    """One turn in the conversation history sent from the client."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    messages: list[ChatMessage]
    local_time: str | None = None


@router.post("/chat")
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Stream an AI response over SSE; 403 if caller is not premium or admin."""
    if not current_user.get("is_premium") and not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Premium subscription required"
        )
    user_id = int(current_user["sub"])
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    def generate():
        """Yield SSE-formatted chunks from the agentic tool loop."""
        try:
            for chunk in run_chat(
                db, messages, user_id, local_time=body.local_time
            ):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
