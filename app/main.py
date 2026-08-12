import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth_routes import router as auth_router
from app.api.chat_routes import router as chat_router
from app.api.exercise_routes import router as exercise_router
from app.api.routine_routes import router as routine_router
from app.api.workout_routes import router as workout_router
from app.db.database import Base, SessionLocal, engine
from app.db.seed import seed_demo_data, seed_exercises

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


@app.get("/routines")
def routines_page():
    """Serve the routines management page."""
    return FileResponse("app/static/routines.html", headers=NO_CACHE)


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


@app.get("/login")
def login_page():
    """Serve the login page."""
    return FileResponse("app/static/login.html", headers=NO_CACHE)


@app.get("/register")
def register_page():
    """Serve the registration page."""
    return FileResponse("app/static/register.html", headers=NO_CACHE)


@app.get("/")
def index():
    """Serve the dashboard page."""
    return FileResponse("app/static/dashboard.html", headers=NO_CACHE)


app.include_router(auth_router, prefix="/api")
app.include_router(workout_router, prefix="/api")
app.include_router(exercise_router, prefix="/api")
app.include_router(routine_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
def health():
    """Return a simple health check response."""
    return {"status": "ok"}
