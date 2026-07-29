from collections import defaultdict
from typing import Optional
from sqlalchemy.orm import Session
from app.model.models import ExerciseDef, MuscleGroup, Exercise, Workout
from app.api.schemas import CreateExerciseSchema, ExerciseUpdate


def get_all_exercises(db: Session) -> list[ExerciseDef]:
    return db.query(ExerciseDef).order_by(ExerciseDef.name).all()


def get_exercise(db: Session, exercise_id: int) -> Optional[ExerciseDef]:
    return db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()


def get_all_muscle_groups(db: Session) -> list[MuscleGroup]:
    return db.query(MuscleGroup).order_by(MuscleGroup.name).all()


def create_exercise(db: Session, data: CreateExerciseSchema) -> ExerciseDef:
    muscle_groups = db.query(MuscleGroup).filter(MuscleGroup.id.in_(data.muscle_group_ids)).all()
    exercise = ExerciseDef(
        name=data.name,
        equipment=data.equipment,
        target=data.target,
        instructions=data.instructions,
        muscle_groups=muscle_groups,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


def update_exercise(db: Session, exercise_id: int, data: ExerciseUpdate) -> Optional[ExerciseDef]:
    exercise = db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
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
    if data.target is not None:
        exercise.target = data.target
    if data.instructions is not None:
        exercise.instructions = data.instructions

    if data.muscle_group_ids is not None:
        exercise.muscle_groups = db.query(MuscleGroup).filter(
            MuscleGroup.id.in_(data.muscle_group_ids)
        ).all()

    db.commit()
    db.refresh(exercise)
    return exercise


def delete_exercise(db: Session, exercise_id: int) -> bool:
    exercise = db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
    if not exercise:
        return False

    has_sets = db.query(Exercise).filter(Exercise.exercise_id == exercise_id).first()
    if has_sets:
        raise ValueError("has_history")

    db.delete(exercise)
    db.commit()
    return True


def get_exercise_progression(db: Session, exercise_id: int):
    exercise = db.query(ExerciseDef).filter(ExerciseDef.id == exercise_id).first()
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
    for sid, data in sorted(session_map.items(), key=lambda x: x[1]["logged_at"]):
        s_sets = data["sets"]
        weights = [s.weight_lbs for s in s_sets if s.weight_lbs is not None]
        volume = round(sum(s.reps * s.weight_lbs for s in s_sets if s.weight_lbs is not None), 1) if weights else None
        sessions.append({
            "session_id": sid,
            "logged_at": data["logged_at"],
            "sets": [{"set_number": s.set_number, "reps": s.reps, "weight_lbs": s.weight_lbs} for s in s_sets],
            "volume": volume,
            "best_set_weight": max(weights) if weights else None,
        })

    return exercise, sessions
