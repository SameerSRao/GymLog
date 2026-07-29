from collections import defaultdict

from sqlalchemy.orm import Session, joinedload

from app.api.schemas import WorkoutRequest
from app.model.models import Exercise, ExerciseDef, Workout


def build_workout_detailed(db: Session, session: Workout) -> dict:
    """Build the detailed workout dict used by WorkoutDetailed, grouping sets by exercise."""
    sets = (
        db.query(Exercise)
        .options(
            joinedload(Exercise.exercise_def).joinedload(ExerciseDef.muscle_groups)
        )
        .filter(Exercise.session_id == session.id)
        .order_by(Exercise.set_number)
        .all()
    )

    grouped: dict[int, list] = defaultdict(list)
    for ex_set in sets:
        grouped[ex_set.exercise_id].append(ex_set)

    exercises = [
        {
            "exercise_id": exercise_id,
            "name": set_list[0].exercise_def.name,
            "muscle_groups": [
                {"id": mg.id, "name": mg.name}
                for mg in set_list[0].exercise_def.muscle_groups
            ],
            "sets": [
                {"reps": s.reps, "weight_lbs": s.weight_lbs}
                for s in set_list
            ],
        }
        for exercise_id, set_list in grouped.items()
    ]

    return {
        "session_id": session.id,
        "logged_at": session.logged_at,
        "notes": session.raw_input,
        "exercises": exercises,
    }


def log_workout(db: Session, workout: WorkoutRequest) -> Workout:
    """Persist a new workout session with all its exercise sets and return it."""
    session = (
        Workout(raw_input=workout.notes, logged_at=workout.logged_at)
        if workout.logged_at
        else Workout(raw_input=workout.notes)
    )
    db.add(session)
    db.flush()

    for exercise in workout.exercises:
        for j, s in enumerate(exercise.sets):
            db.add(Exercise(
                session_id=session.id,
                exercise_id=exercise.exercise_id,
                set_number=j + 1,
                reps=s.reps,
                weight_lbs=s.weight_lbs,
            ))

    db.commit()
    db.refresh(session)
    return session


def get_workout(db: Session, session_id: int) -> Workout | None:
    """Return a workout session by ID, or None if not found."""
    return db.query(Workout).filter(Workout.id == session_id).first()


def get_all_workouts(db: Session) -> list[Workout]:
    """Return all workout sessions ordered by date descending."""
    return db.query(Workout).order_by(Workout.logged_at.desc()).all()


def update_workout(
    db: Session, session_id: int, workout: WorkoutRequest
) -> Workout | None:
    """Replace all sets in an existing workout session; returns None if not found."""
    session = db.query(Workout).filter(Workout.id == session_id).first()
    if not session:
        return None

    session.raw_input = workout.notes
    db.query(Exercise).filter(Exercise.session_id == session_id).delete()

    for exercise in workout.exercises:
        for j, s in enumerate(exercise.sets):
            db.add(Exercise(
                session_id=session.id,
                exercise_id=exercise.exercise_id,
                set_number=j + 1,
                reps=s.reps,
                weight_lbs=s.weight_lbs,
            ))

    db.commit()
    db.refresh(session)
    return session


def delete_workout(db: Session, session_id: int) -> bool:
    """Delete a workout session and all its sets; returns False if not found."""
    session = db.query(Workout).filter(Workout.id == session_id).first()
    if not session:
        return False
    db.delete(session)
    db.commit()
    return True
