from collections import defaultdict

from sqlalchemy.orm import Session, joinedload

from app.exercises.schemas import CreateExerciseSchema, ExerciseUpdate
from app.db.models import Exercise, ExerciseDef, MuscleGroup, Workout


def get_all_exercises(db: Session, user_id: int) -> list[ExerciseDef]:
    """Return global exercises plus caller's custom exercises, alphabetically."""
    return (
        db.query(ExerciseDef)
        .options(joinedload(ExerciseDef.muscle_groups))
        .filter(
            (ExerciseDef.user_id.is_(None)) |
            (ExerciseDef.user_id == user_id)
        )
        .order_by(ExerciseDef.name)
        .all()
    )


def get_exercise(db: Session, exercise_id: int) -> ExerciseDef | None:
    """Return a single exercise by ID, or None if not found."""
    return (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )


def get_all_muscle_groups(db: Session) -> list[MuscleGroup]:
    """Return all muscle groups ordered alphabetically by name."""
    return db.query(MuscleGroup).order_by(MuscleGroup.name).all()


def create_exercise(
    db: Session, data: CreateExerciseSchema, user_id: int
) -> ExerciseDef:
    """Create and persist a new custom exercise owned by user_id."""
    muscle_groups = (
        db.query(MuscleGroup)
        .filter(MuscleGroup.id.in_(data.muscle_group_ids))
        .all()
    )
    exercise = ExerciseDef(
        name=data.name,
        equipment=data.equipment,
        instructions=data.instructions,
        muscle_groups=muscle_groups,
        user_id=user_id,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


def update_exercise(
    db: Session,
    exercise_id: int,
    data: ExerciseUpdate,
    user_id: int,
    is_admin: bool = False,
) -> ExerciseDef | None:
    """Partially update an exercise; returns None if not found.

    Raises ValueError('forbidden') if the caller lacks permission.
    Raises ValueError('name_conflict') if the new name is taken in the same
    scope.
    """
    exercise = (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )
    if not exercise:
        return None

    if exercise.user_id is None and not is_admin:
        raise ValueError("forbidden")
    if (
        exercise.user_id is not None
        and exercise.user_id != user_id
        and not is_admin
    ):
        raise ValueError("forbidden")

    if data.name is not None and data.name != exercise.name:
        conflict = db.query(ExerciseDef).filter(
            ExerciseDef.name == data.name,
            ExerciseDef.id != exercise_id,
            ExerciseDef.user_id == exercise.user_id,
        ).first()
        if conflict:
            raise ValueError("name_conflict")
        exercise.name = data.name

    if data.equipment is not None:
        exercise.equipment = data.equipment
    if data.instructions is not None:
        exercise.instructions = data.instructions
    if data.muscle_group_ids is not None:
        exercise.muscle_groups = (
            db.query(MuscleGroup)
            .filter(MuscleGroup.id.in_(data.muscle_group_ids))
            .all()
        )

    db.commit()
    db.refresh(exercise)
    return exercise


def delete_exercise(
    db: Session,
    exercise_id: int,
    user_id: int,
    is_admin: bool = False,
) -> bool:
    """Delete an exercise; returns False if not found.

    Raises ValueError('forbidden') if the caller lacks permission.
    Raises ValueError('has_history') if the exercise has logged sets.
    """
    exercise = (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )
    if not exercise:
        return False

    if exercise.user_id is None and not is_admin:
        raise ValueError("forbidden")
    if (
        exercise.user_id is not None
        and exercise.user_id != user_id
        and not is_admin
    ):
        raise ValueError("forbidden")

    if db.query(Exercise).filter(
        Exercise.exercise_id == exercise_id
    ).first():
        raise ValueError("has_history")

    db.delete(exercise)
    db.commit()
    return True


def get_exercise_progression(
    db: Session, exercise_id: int, user_id: int
):
    """Return (exercise, sessions) for caller's progression with this exercise.

    sessions is a list of dicts sorted chronologically, each with
    session_id, logged_at, sets, volume, and best_set_weight.
    Returns (None, []) if the exercise does not exist.
    """
    exercise = (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )
    if not exercise:
        return None, []

    rows = (
        db.query(Exercise, Workout.logged_at)
        .join(Workout, Exercise.session_id == Workout.id)
        .filter(
            Exercise.exercise_id == exercise.id,
            Workout.user_id == user_id,
        )
        .order_by(Workout.logged_at.asc(), Exercise.set_number.asc())
        .all()
    )

    session_map: dict = defaultdict(lambda: {"logged_at": None, "sets": []})
    for ex_set, logged_at in rows:
        sid = ex_set.session_id
        session_map[sid]["logged_at"] = logged_at
        session_map[sid]["sets"].append(ex_set)

    sessions = []
    for sid, data in sorted(
        session_map.items(), key=lambda x: x[1]["logged_at"]
    ):
        s_sets = data["sets"]
        weights = [s.weight_lbs for s in s_sets if s.weight_lbs is not None]
        volume = (
            round(
                sum(
                    s.reps * s.weight_lbs
                    for s in s_sets
                    if s.weight_lbs is not None
                ),
                1,
            )
            if weights
            else None
        )
        sessions.append({
            "session_id": sid,
            "logged_at": data["logged_at"],
            "sets": [
                {
                    "set_number": s.set_number,
                    "reps": s.reps,
                    "weight_lbs": s.weight_lbs,
                }
                for s in s_sets
            ],
            "volume": volume,
            "best_set_weight": max(weights) if weights else None,
        })

    return exercise, sessions
