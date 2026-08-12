import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.db.database import Base, SessionLocal, engine
from app.db.seed import seed_demo_data, seed_exercises
from app.exercises.routes import router as exercise_router
from app.routines.routes import router as routine_router
from app.workouts.routes import router as workout_router

if not os.getenv("TESTING"):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_exercises(db)
        seed_demo_data(db)

_dev = os.getenv("ENVIRONMENT") == "development"
app = FastAPI(
    docs_url="/docs" if _dev else None,
    redoc_url="/redoc" if _dev else None,
)

_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(workout_router, prefix="/api")
app.include_router(exercise_router, prefix="/api")
app.include_router(routine_router, prefix="/api")


@app.get("/health")
def health():
    """Return a simple health check response."""
    return {"status": "ok"}
