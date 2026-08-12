from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user, require_not_demo
from app.db.database import get_db
from app.db.models import ExerciseDef, Routine
from app.routines.schemas import (
    RoutineCreate,
    RoutineDetail,
    RoutineExerciseDetail,
    RoutineListItem,
    RoutineUpdate,
)
from app.routines.service import (
    create_routine,
    delete_routine,
    get_all_routines,
    get_routine,
    update_routine,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


def _validate_exercise_ids(db: Session, exercises: list) -> list[int]:
    """Return exercise_ids from the request that do not exist in the DB."""
    requested = {ex.exercise_id for ex in exercises}
    found = {
        row.id
        for row in db.query(ExerciseDef)
        .filter(ExerciseDef.id.in_(requested))
        .all()
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
def add_routine(
    data: RoutineCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Create a new routine for the current user; 409 if name is already taken."""
    user_id = int(current_user["sub"])
    invalid = _validate_exercise_ids(db, data.exercises)
    if invalid:
        raise HTTPException(
            status_code=400, detail=f"Invalid exercise ids: {invalid}"
        )
    try:
        routine = create_routine(db, data, user_id)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="A routine with that name already exists",
            )
        raise
    return _to_detail(get_routine(db, routine.id, user_id))


@router.get("/routines", response_model=list[RoutineListItem])
def list_routines(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return all routines for the current user ordered by name."""
    user_id = int(current_user["sub"])
    routines = get_all_routines(db, user_id)
    return [
        RoutineListItem(
            id=r.id,
            name=r.name,
            exercise_count=len(r.exercises),
            created_at=r.created_at,
        )
        for r in routines
    ]


@router.get("/routine/{routine_id}", response_model=RoutineDetail)
def fetch_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return full detail for a routine; 404 if not found or not owned."""
    routine = get_routine(db, routine_id, int(current_user["sub"]))
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    return _to_detail(routine)


@router.put("/routine/{routine_id}", response_model=RoutineDetail)
def replace_routine(
    routine_id: int,
    data: RoutineUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Replace a routine's name and exercises; 404 if not owned, 409 on conflict."""
    user_id = int(current_user["sub"])
    invalid = _validate_exercise_ids(db, data.exercises)
    if invalid:
        raise HTTPException(
            status_code=400, detail=f"Invalid exercise ids: {invalid}"
        )
    try:
        routine = update_routine(db, routine_id, data, user_id)
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(
                status_code=409,
                detail="A routine with that name already exists",
            )
        raise
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    return _to_detail(get_routine(db, routine.id, user_id))


@router.delete("/routine/{routine_id}")
def remove_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_not_demo),
):
    """Delete a routine owned by the current user; 404 if not found."""
    if not delete_routine(db, routine_id, int(current_user["sub"])):
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"deleted": routine_id}
