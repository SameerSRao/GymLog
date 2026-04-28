from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.schemas import WorkoutRequest, WorkoutResponse, WorkoutDetailed, ExerciseSchema, SetSchema
from app.services.workout_service import log_workout, get_workout, get_all_workouts, update_workout, delete_workout
from collections import defaultdict

router = APIRouter()


@router.post("/workouts", response_model=WorkoutResponse)
def create_workout(workout: WorkoutRequest, db: Session = Depends(get_db)):
    session = log_workout(db, workout)
    return WorkoutResponse(
        session_id=session.id,
        logged_at=session.logged_at,
        exercises_logged=len(workout.exercises),
        sets_logged=sum(len(e.sets) for e in workout.exercises),
    )


@router.get("/workouts", response_model=list[WorkoutResponse])
def list_workouts(db: Session = Depends(get_db)):
    sessions = get_all_workouts(db)
    return [
        WorkoutResponse(
            session_id=s.id,
            logged_at=s.logged_at,
            exercises_logged=len(s.sets),
            sets_logged=len(s.sets),
        )
        for s in sessions
    ]


@router.get("/workout/{session_id}", response_model=WorkoutDetailed)
def fetch_workout(session_id: int, db: Session = Depends(get_db)):
    session = get_workout(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")

    grouped = defaultdict(list)
    for ex_set in session.sets:
        grouped[ex_set.exercise_name].append(ex_set)

    exercises = [
        ExerciseSchema(
            name=name,
            muscle_group=sets[0].muscle_group,
            sets=[SetSchema(reps=ex.reps, weight_lbs=ex.weight_lbs) for ex in sets]
        )
        for name, sets in grouped.items()
    ]

    return WorkoutDetailed(session_id=session_id, logged_at=session.logged_at, exercises=exercises)


@router.put("/workout/{session_id}", response_model=WorkoutDetailed)
def replace_workout(session_id: int, workout: WorkoutRequest, db: Session = Depends(get_db)):
    session = update_workout(db, session_id, workout)
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")

    exercises = [
        ExerciseSchema(
            name=exercise.name,
            muscle_group=exercise.muscle_group,
            sets=exercise.sets,
        )
        for exercise in workout.exercises
    ]

    return WorkoutDetailed(session_id=session_id, logged_at=session.logged_at, exercises=exercises)


@router.delete("/workout/{session_id}")
def remove_workout(session_id: int, db: Session = Depends(get_db)):
    if not delete_workout(db, session_id):
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"deleted": session_id}
