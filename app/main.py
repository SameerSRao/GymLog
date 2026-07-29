import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.exercise_routes import router as exercise_router
from app.api.routes import router
from app.db.database import Base, SessionLocal, engine
from app.db.seed import seed_exercises

if not os.getenv("TESTING"):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_exercises(db)

app = FastAPI()

NO_CACHE = {"Cache-Control": "no-cache"}

# HTML page routes — registered before API routers so they take priority
@app.get("/workouts")
def workouts_page():
    """Serve the workouts list page."""
    return FileResponse("app/static/workouts.html", headers=NO_CACHE)


@app.get("/exercises")
def exercises_page():
    """Serve the exercise browser page."""
    return FileResponse("app/static/exercises.html", headers=NO_CACHE)


@app.get("/workout/{session_id}")
def workout_page(session_id: int):
    """Serve the workout detail page for a given session."""
    return FileResponse("app/static/workout.html", headers=NO_CACHE)


@app.get("/exercise/{exercise_id}")
def exercise_page(exercise_id: int):
    """Serve the exercise detail page for a given exercise."""
    return FileResponse("app/static/exercise.html", headers=NO_CACHE)


@app.get("/log")
def log_page():
    """Serve the workout logging page."""
    return FileResponse("app/static/index.html", headers=NO_CACHE)


@app.get("/")
def index():
    """Serve the dashboard page."""
    return FileResponse("app/static/dashboard.html", headers=NO_CACHE)


app.include_router(router, prefix="/api")
app.include_router(exercise_router, prefix="/api")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
def health():
    """Return a simple health check response."""
    return {"status": "ok"}
