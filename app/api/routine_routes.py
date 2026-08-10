from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    RoutineCreate,
    RoutineDetail,
    RoutineExerciseDetail,
    RoutineListItem,
    RoutineUpdate,
)
from app.db.database import get_db
from app.model.models import ExerciseDef, Routine
from app.services.routine_service import (
    create_routine,
    delete_routine,
    get_all_routines,
    get_routine,
    update_routine,
)

router = APIRouter()


def _validate_exercise_ids(
    db: Session, exercises: list
) -> list[int]:
    """Return a list of exercise_ids from the request that do not exist."""
    requested = {ex.exercise_id for ex in exercises}
    found = {
        row.id
        for row in db.query(ExerciseDef).filter(
            ExerciseDef.id.in_(requested)
        ).all()
    }
    return [eid for eid in requested if eid not in found]


def _to_detail(routine: Routine) -> RoutineDetail:
    """Build a RoutineDetail from a fully-loaded Routine ORM object."""
    return RoutineDetail(
        id=routine.id,
        name=routine.name,
        created_at=routine.created_at,
        exercises=[
            RoutineExerciseDetail(
                exercise_id=ex.exercise_id,
                name=ex.exercise_def.name,
                position=ex.position,
                num_sets=ex.num_sets,
            )
            for ex in sorted(routine.exercises, key=lambda e: e.position)
        ],
    )


@router.post("/routines", response_model=RoutineDetail, status_code=201)
def add_routine(data: RoutineCreate, db: Session = Depends(get_db)):
    """Create a new routine; 409 if name is already taken."""
    invalid = _validate_exercise_ids(db, data.exercises)
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid exercise ids: {invalid}",
        )
    try:
        routine = create_routine(db, data)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="A routine with that name already exists",
            )
        raise
    return _to_detail(get_routine(db, routine.id))


@router.get("/routines", response_model=list[RoutineListItem])
def list_routines(db: Session = Depends(get_db)):
    """Return all routines ordered by name with their exercise counts."""
    routines = get_all_routines(db)
    return [
        RoutineListItem(
            id=r.id,
            name=r.name,
            exercise_count=len(r.exercises),
        )
        for r in routines
    ]


@router.get("/routine/{routine_id}", response_model=RoutineDetail)
def fetch_routine(routine_id: int, db: Session = Depends(get_db)):
    """Return full detail for a single routine; 404 if not found."""
    routine = get_routine(db, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    return _to_detail(routine)


@router.put("/routine/{routine_id}", response_model=RoutineDetail)
def replace_routine(
    routine_id: int,
    data: RoutineUpdate,
    db: Session = Depends(get_db),
):
    """Replace a routine's name and exercises.

    Returns 404 if not found, 400 on invalid exercise id, 409 on name
    conflict.
    """
    invalid = _validate_exercise_ids(db, data.exercises)
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid exercise ids: {invalid}",
        )
    try:
        routine = update_routine(db, routine_id, data)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="A routine with that name already exists",
            )
        raise
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    return _to_detail(get_routine(db, routine.id))


@router.delete("/routine/{routine_id}")
def remove_routine(routine_id: int, db: Session = Depends(get_db)):
    """Delete a routine and its exercise slots; 404 if not found."""
    if not delete_routine(db, routine_id):
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"deleted": routine_id}
