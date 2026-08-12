from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth_routes import get_current_user, require_not_demo
from app.api.schemas import (
    ImportResponse,
    WorkoutDetailed,
    WorkoutImportRequest,
    WorkoutRequest,
    WorkoutResponse,
)
from app.db.database import get_db
from app.services.workout_service import (
    build_workout_detailed,
    delete_workout,
    get_all_workouts,
    get_workout,
    import_workouts,
    log_workout,
    update_workout,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/workouts", response_model=WorkoutResponse)
def create_workout(
    workout: WorkoutRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Log a new workout session and return a summary."""
    user_id = int(current_user["sub"])
    session = log_workout(db, workout, user_id)
    return WorkoutResponse(
        session_id=session.id,
        logged_at=session.logged_at,
        exercises_logged=len(workout.exercises),
        sets_logged=sum(len(e.sets) for e in workout.exercises),
    )


@router.post("/workouts/import", response_model=ImportResponse)
def batch_import_workouts(
    sessions: list[WorkoutImportRequest],
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Bulk-insert workout sessions; admin only, demo users blocked."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Admin access required"
        )
    return import_workouts(db, sessions, int(current_user["sub"]))


@router.get("/workouts", response_model=list[WorkoutResponse])
def list_workouts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return all workout sessions for the current user, newest first."""
    user_id = int(current_user["sub"])
    sessions = get_all_workouts(db, user_id)
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
def fetch_workout(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return full detail for a single workout; 404 if not found or not owned."""
    session = get_workout(db, session_id, int(current_user["sub"]))
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return WorkoutDetailed(**build_workout_detailed(db, session))


@router.put("/workout/{session_id}", response_model=WorkoutDetailed)
def replace_workout(
    session_id: int,
    workout: WorkoutRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Replace all exercises in a workout; 404 if not found or not owned."""
    session = update_workout(
        db, session_id, workout, int(current_user["sub"])
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return WorkoutDetailed(**build_workout_detailed(db, session))


@router.delete("/workout/{session_id}")
def remove_workout(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Delete a workout and all its sets; 404 if not found or not owned."""
    if not delete_workout(db, session_id, int(current_user["sub"])):
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"deleted": session_id}
