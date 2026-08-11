import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_routes import get_current_user
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


@router.post("/chat")
def chat(body: ChatRequest, db: Session = Depends(get_db)):
    """Stream an AI response over SSE; client owns conversation history."""
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    def generate():
        """Yield SSE-formatted chunks from the agentic tool loop."""
        try:
            for chunk in run_chat(db, messages):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
