from pydantic import BaseModel


class ChatMessage(BaseModel):
    """One turn in the conversation history sent from the client."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    messages: list[ChatMessage]
    local_time: str | None = None
