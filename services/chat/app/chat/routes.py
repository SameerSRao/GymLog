import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.chat.schemas import ChatRequest
from app.chat.service import run_chat
from app.client.api_client import api_client

router = APIRouter()
_bearer = HTTPBearer()


@router.post("/chat")
def chat(
    body: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    """Stream AI response over SSE; 401/403 propagated from core API."""
    token = credentials.credentials
    try:
        user = api_client.get_me(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    if user.get("is_demo"):
        raise HTTPException(
            status_code=403,
            detail="Demo accounts cannot perform this action",
        )
    if not user.get("is_premium") and not user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Premium subscription required"
        )

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    def generate():
        """Yield SSE-formatted chunks from the agentic tool loop."""
        try:
            for chunk in run_chat(token, messages, local_time=body.local_time):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
