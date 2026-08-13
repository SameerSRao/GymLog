from fastapi import FastAPI

from app.chat.routes import router as chat_router

app = FastAPI(docs_url=None, redoc_url=None)
app.include_router(chat_router, prefix="/api")


@app.get("/health")
def health():
    """Return a simple health check response."""
    return {"status": "ok"}
