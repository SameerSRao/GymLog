from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.auth_routes import get_current_user

from app.api.schemas import (
    CreateExerciseSchema,
    ExerciseDefSchema,
    ExerciseProgressionSchema,
    ExerciseUpdate,
    MuscleGroupSchema,
    SessionSummary,
    SetDetail,
)
from app.db.database import get_db
from app.services.exercise_service import (
    create_exercise,
    delete_exercise,
    get_all_exercises,
    get_all_muscle_groups,
    get_exercise,
    get_exercise_progression,
    update_exercise,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/muscle-groups", response_model=list[MuscleGroupSchema])
def list_muscle_groups(db: Session = Depends(get_db)):
    """Return all muscle groups in alphabetical order."""
    return get_all_muscle_groups(db)


@router.get("/exercises", response_model=list[ExerciseDefSchema])
def list_exercises(db: Session = Depends(get_db)):
    """Return all exercise definitions in alphabetical order."""
    return get_all_exercises(db)


@router.post("/exercises", response_model=ExerciseDefSchema, status_code=201)
def add_exercise(data: CreateExerciseSchema, db: Session = Depends(get_db)):
    """Create a new exercise; returns 400 if any muscle group ID is invalid."""
    muscle_groups = get_all_muscle_groups(db)
    valid_ids = {mg.id for mg in muscle_groups}
    invalid = [i for i in data.muscle_group_ids if i not in valid_ids]
    if invalid:
        raise HTTPException(
            status_code=400, detail=f"Invalid muscle group ids: {invalid}"
        )
    return create_exercise(db, data)


@router.get("/exercise/{exercise_id}/info", response_model=ExerciseDefSchema)
def get_exercise_info(exercise_id: int, db: Session = Depends(get_db)):
    """Return a single exercise by ID; 404 if not found."""
    exercise = get_exercise(db, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


@router.put("/exercise/{exercise_id}", response_model=ExerciseDefSchema)
def edit_exercise(
    exercise_id: int,
    data: ExerciseUpdate,
    db: Session = Depends(get_db),
):
    """Partially update an exercise; 404 if not found, 409 on name conflict, 400 on invalid muscle group."""
    if data.muscle_group_ids is not None:
        muscle_groups = get_all_muscle_groups(db)
        valid_ids = {mg.id for mg in muscle_groups}
        invalid = [i for i in data.muscle_group_ids if i not in valid_ids]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid muscle group ids: {invalid}",
            )
    try:
        exercise = update_exercise(db, exercise_id, data)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="An exercise with that name already exists",
            )
        raise
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


@router.delete("/exercise/{exercise_id}", status_code=204)
def remove_exercise(exercise_id: int, db: Session = Depends(get_db)):
    """Delete an exercise; 404 if not found, 409 if it has logged workout history."""
    try:
        found = delete_exercise(db, exercise_id)
    except ValueError as e:
        if str(e) == "has_history":
            raise HTTPException(
                status_code=409,
                detail="Exercise has logged history and cannot be deleted",
            )
        raise
    if not found:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return Response(status_code=204)


@router.get(
    "/exercise/{exercise_id}/progression",
    response_model=ExerciseProgressionSchema,
)
def get_progression(exercise_id: int, db: Session = Depends(get_db)):
    """Return an exercise's progression history across all workout sessions; 404 if not found."""
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
