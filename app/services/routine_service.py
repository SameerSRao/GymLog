from sqlalchemy.orm import Session, joinedload

from app.api.schemas import RoutineCreate, RoutineUpdate
from app.model.models import Routine, RoutineExercise


def create_routine(
    db: Session, data: RoutineCreate, user_id: int
) -> Routine:
    """Create a new routine for user_id.

    Raises ValueError('name_conflict') if a routine with that name
    already belongs to the same user.
    """
    if db.query(Routine).filter(
        Routine.name == data.name, Routine.user_id == user_id
    ).first():
        raise ValueError("name_conflict")
    routine = Routine(name=data.name, user_id=user_id)
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


def get_all_routines(db: Session, user_id: int) -> list[Routine]:
    """Return all routines for user_id with exercises eager-loaded, by name."""
    return (
        db.query(Routine)
        .options(joinedload(Routine.exercises))
        .filter(Routine.user_id == user_id)
        .order_by(Routine.name)
        .all()
    )


def get_routine(
    db: Session, routine_id: int, user_id: int
) -> Routine | None:
    """Return a routine owned by user_id with exercise definitions loaded, or None."""
    return (
        db.query(Routine)
        .options(
            joinedload(Routine.exercises).joinedload(
                RoutineExercise.exercise_def
            )
        )
        .filter(Routine.id == routine_id, Routine.user_id == user_id)
        .first()
    )


def update_routine(
    db: Session, routine_id: int, data: RoutineUpdate, user_id: int
) -> Routine | None:
    """Replace a routine's name and exercises for user_id; returns None if not found.

    Raises ValueError('name_conflict') if the new name is taken by another
    routine belonging to the same user.
    """
    routine = (
        db.query(Routine)
        .filter(Routine.id == routine_id, Routine.user_id == user_id)
        .first()
    )
    if not routine:
        return None
    conflict = db.query(Routine).filter(
        Routine.name == data.name,
        Routine.id != routine_id,
        Routine.user_id == user_id,
    ).first()
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


def delete_routine(
    db: Session, routine_id: int, user_id: int
) -> bool:
    """Delete a routine owned by user_id; returns False if not found."""
    routine = (
        db.query(Routine)
        .filter(Routine.id == routine_id, Routine.user_id == user_id)
        .first()
    )
    if not routine:
        return False
    db.delete(routine)
    db.commit()
    return True
