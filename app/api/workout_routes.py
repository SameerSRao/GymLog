from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import WorkoutDetailed, WorkoutRequest, WorkoutResponse
from app.db.database import get_db
from app.services.workout_service import (
    build_workout_detailed,
    delete_workout,
    get_all_workouts,
    get_workout,
    log_workout,
    update_workout,
)

router = APIRouter()


@router.post("/workouts", response_model=WorkoutResponse)
def create_workout(workout: WorkoutRequest, db: Session = Depends(get_db)):
    """Log a new workout session and return a summary of what was recorded."""
    session = log_workout(db, workout)
    return WorkoutResponse(
        session_id=session.id,
        logged_at=session.logged_at,
        exercises_logged=len(workout.exercises),
        sets_logged=sum(len(e.sets) for e in workout.exercises),
    )


@router.get("/workouts", response_model=list[WorkoutResponse])
def list_workouts(db: Session = Depends(get_db)):
    """Return all workout sessions ordered by date descending."""
    sessions = get_all_workouts(db)
    return [
        WorkoutResponse(
            session_id=s.id,
            logged_at=s.logged_at,
            exercises_logged=len({ex.exercise_id for ex in s.sets}),
            sets_logged=len(s.sets),
        )
        for s in sessions
    ]


@router.get("/workout/{session_id}", response_model=WorkoutDetailed)
def fetch_workout(session_id: int, db: Session = Depends(get_db)):
    """Return full detail for a single workout session; 404 if not found."""
    session = get_workout(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return WorkoutDetailed(**build_workout_detailed(db, session))


@router.put("/workout/{session_id}", response_model=WorkoutDetailed)
def replace_workout(
    session_id: int,
    workout: WorkoutRequest,
    db: Session = Depends(get_db),
):
    """Replace all exercises in a workout session; 404 if not found."""
    session = update_workout(db, session_id, workout)
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return WorkoutDetailed(**build_workout_detailed(db, session))


@router.delete("/workout/{session_id}")
def remove_workout(session_id: int, db: Session = Depends(get_db)):
    """Delete a workout session and all its sets; 404 if not found."""
    if not delete_workout(db, session_id):
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"deleted": session_id}
