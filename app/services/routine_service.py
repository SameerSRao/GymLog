from sqlalchemy.orm import Session, joinedload

from app.api.schemas import RoutineCreate, RoutineUpdate
from app.model.models import Routine, RoutineExercise


def create_routine(db: Session, data: RoutineCreate) -> Routine:
    """Create a new routine; raises ValueError('name_conflict') if name taken."""
    if db.query(Routine).filter(Routine.name == data.name).first():
        raise ValueError("name_conflict")
    routine = Routine(name=data.name)
    db.add(routine)
    db.flush()
    for ex in data.exercises:
        db.add(RoutineExercise(
            routine_id=routine.id,
            exercise_id=ex.exercise_id,
            position=ex.position,
            num_sets=ex.num_sets,
        ))
    db.commit()
    db.refresh(routine)
    return routine


def get_all_routines(db: Session) -> list[Routine]:
    """Return all routines with exercises eager-loaded, ordered by name."""
    return (
        db.query(Routine)
        .options(joinedload(Routine.exercises))
        .order_by(Routine.name)
        .all()
    )


def get_routine(db: Session, routine_id: int) -> Routine | None:
    """Return a routine by ID with exercise definitions loaded, or None."""
    return (
        db.query(Routine)
        .options(
            joinedload(Routine.exercises).joinedload(
                RoutineExercise.exercise_def
            )
        )
        .filter(Routine.id == routine_id)
        .first()
    )


def update_routine(
    db: Session, routine_id: int, data: RoutineUpdate
) -> Routine | None:
    """Replace a routine's name and exercises; returns None if not found.

    Raises ValueError('name_conflict') if the new name is taken by another
    routine.
    """
    routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if not routine:
        return None
    conflict = (
        db.query(Routine)
        .filter(Routine.name == data.name, Routine.id != routine_id)
        .first()
    )
    if conflict:
        raise ValueError("name_conflict")
    routine.name = data.name
    db.query(RoutineExercise).filter(
        RoutineExercise.routine_id == routine_id
    ).delete()
    for ex in data.exercises:
        db.add(RoutineExercise(
            routine_id=routine.id,
            exercise_id=ex.exercise_id,
            position=ex.position,
            num_sets=ex.num_sets,
        ))
    db.commit()
    db.refresh(routine)
    return routine


def delete_routine(db: Session, routine_id: int) -> bool:
    """Delete a routine and its exercise slots; returns False if not found."""
    routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if not routine:
        return False
    db.delete(routine)
    db.commit()
    return True
