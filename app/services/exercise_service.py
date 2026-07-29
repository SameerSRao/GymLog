from collections import defaultdict

from sqlalchemy.orm import Session

from app.api.schemas import CreateExerciseSchema, ExerciseUpdate
from app.model.models import Exercise, ExerciseDef, MuscleGroup, Workout


def get_all_exercises(db: Session) -> list[ExerciseDef]:
    """Return all exercises ordered alphabetically by name."""
    return db.query(ExerciseDef).order_by(ExerciseDef.name).all()


def get_exercise(db: Session, exercise_id: int) -> ExerciseDef | None:
    """Return a single exercise by ID, or None if not found."""
    return (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )


def get_all_muscle_groups(db: Session) -> list[MuscleGroup]:
    """Return all muscle groups ordered alphabetically by name."""
    return db.query(MuscleGroup).order_by(MuscleGroup.name).all()


def create_exercise(db: Session, data: CreateExerciseSchema) -> ExerciseDef:
    """Create and persist a new exercise with the given muscle groups."""
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
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


def update_exercise(
    db: Session, exercise_id: int, data: ExerciseUpdate
) -> ExerciseDef | None:
    """Partially update an exercise; returns None if not found.

    Raises ValueError('name_conflict') if the new name is already taken by
    another exercise.
    """
    exercise = (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )
    if not exercise:
        return None

    if data.name is not None and data.name != exercise.name:
        conflict = db.query(ExerciseDef).filter(
            ExerciseDef.name == data.name,
            ExerciseDef.id != exercise_id,
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


def delete_exercise(db: Session, exercise_id: int) -> bool:
    """Delete an exercise; returns False if not found.

    Raises ValueError('has_history') if the exercise has logged sets.
    """
    exercise = (
        db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    )
    if not exercise:
        return False

    has_sets = (
        db.query(Exercise).filter(Exercise.exercise_id == exercise_id).first()
    )
    if has_sets:
        raise ValueError("has_history")

    db.delete(exercise)
    db.commit()
    return True


def get_exercise_progression(db: Session, exercise_id: int):
    """Return (exercise, sessions) for an exercise's progression history.

    sessions is a list of dicts sorted chronologically, each containing
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
        .filter(Exercise.exercise_id == exercise.id)
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
