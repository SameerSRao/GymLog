from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.schemas import (
    ExerciseDefSchema, CreateExerciseSchema, MuscleGroupSchema,
    ExerciseProgressionSchema, SessionSummary, SetDetail,
)
from app.services.exercise_service import (
    get_all_exercises, get_exercise, get_all_muscle_groups,
    create_exercise, get_exercise_progression,
)

router = APIRouter()


@router.get("/muscle-groups", response_model=list[MuscleGroupSchema])
def list_muscle_groups(db: Session = Depends(get_db)):
    return get_all_muscle_groups(db)


@router.get("/exercises", response_model=list[ExerciseDefSchema])
def list_exercises(db: Session = Depends(get_db)):
    return get_all_exercises(db)


@router.post("/exercises", response_model=ExerciseDefSchema, status_code=201)
def add_exercise(data: CreateExerciseSchema, db: Session = Depends(get_db)):
    muscle_groups = get_all_muscle_groups(db)
    valid_ids = {mg.id for mg in muscle_groups}
    invalid = [i for i in data.muscle_group_ids if i not in valid_ids]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid muscle group ids: {invalid}")
    return create_exercise(db, data)


@router.get("/exercise/{exercise_id}/info", response_model=ExerciseDefSchema)
def get_exercise_info(exercise_id: int, db: Session = Depends(get_db)):
    exercise = get_exercise(db, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


@router.get("/exercise/{exercise_id}/progression", response_model=ExerciseProgressionSchema)
def get_progression(exercise_id: int, db: Session = Depends(get_db)):
    exercise, sessions = get_exercise_progression(db, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ExerciseProgressionSchema(
        exercise_id=exercise.id,
        exercise_name=exercise.name,
        sessions=[
            SessionSummary(
                session_id=s["session_id"],
                logged_at=s["logged_at"],
                sets=[SetDetail(**d) for d in s["sets"]],
                volume=s["volume"],
                best_set_weight=s["best_set_weight"],
            )
            for s in sessions
        ],
    )
