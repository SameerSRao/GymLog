from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.db.database import engine, Base
from app.model.models import Workout, Exercise
from app.api.routes import router

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse("app/static/index.html")
