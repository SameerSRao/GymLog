from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.db.database import get_db
from app.api.schemas import (
    WorkoutRequest, WorkoutResponse, WorkoutDetailed, ExerciseSchema,
    SetSchema, MuscleGroupSchema,
)
from app.model.models import Exercise, ExerciseDef
from app.services.workout_service import log_workout, get_workout, get_all_workouts, update_workout, delete_workout
from collections import defaultdict

router = APIRouter()


def _build_workout_detailed(session, db: Session) -> WorkoutDetailed:
    sets = (
        db.query(Exercise)
        .options(joinedload(Exercise.exercise_def).joinedload(ExerciseDef.muscle_groups))
        .filter(Exercise.session_id == session.id)
        .order_by(Exercise.set_number)
        .all()
    )

    grouped: dict[int, list] = defaultdict(list)
    for ex_set in sets:
        grouped[ex_set.exercise_id].append(ex_set)

    exercises = [
        ExerciseSchema(
            exercise_id=exercise_id,
            name=set_list[0].exercise_def.name,
            muscle_groups=[
                MuscleGroupSchema(id=mg.id, name=mg.name)
                for mg in set_list[0].exercise_def.muscle_groups
            ],
            sets=[SetSchema(reps=s.reps, weight_lbs=s.weight_lbs) for s in set_list],
        )
        for exercise_id, set_list in grouped.items()
    ]

    return WorkoutDetailed(session_id=session.id, logged_at=session.logged_at, exercises=exercises)


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
            exercises_logged=len(set(ex.exercise_id for ex in s.sets)),
            sets_logged=len(s.sets),
        )
        for s in sessions
    ]


@router.get("/workout/{session_id}", response_model=WorkoutDetailed)
def fetch_workout(session_id: int, db: Session = Depends(get_db)):
    session = get_workout(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return _build_workout_detailed(session, db)


@router.put("/workout/{session_id}", response_model=WorkoutDetailed)
def replace_workout(session_id: int, workout: WorkoutRequest, db: Session = Depends(get_db)):
    session = update_workout(db, session_id, workout)
    if session is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return _build_workout_detailed(session, db)


@router.delete("/workout/{session_id}")
def remove_workout(session_id: int, db: Session = Depends(get_db)):
    if not delete_workout(db, session_id):
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"deleted": session_id}
