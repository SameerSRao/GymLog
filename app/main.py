from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.db.database import engine, Base, SessionLocal
from app.model.models import Workout, Exercise, ExerciseDef, MuscleGroup
from app.api.routes import router
from app.api.exercise_routes import router as exercise_router
from app.db.seed import seed_exercises

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed_exercises(db)

app = FastAPI()

# HTML page routes — registered before API routers so they take priority
@app.get("/workouts")
def workouts_page():
    return FileResponse("app/static/workouts.html")

@app.get("/workout/{session_id}")
def workout_page(session_id: int):
    return FileResponse("app/static/workout.html")

@app.get("/exercise/{exercise_id}")
def exercise_page(exercise_id: int):
    return FileResponse("app/static/exercise.html")

app.include_router(router, prefix="/api")
app.include_router(exercise_router, prefix="/api")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse("app/static/index.html")
