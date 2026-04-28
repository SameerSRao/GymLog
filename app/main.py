from fastapi import FastAPI
from app.db.database import engine, Base
from app.model.models import Workout, Exercise
from app.api.routes import router

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
