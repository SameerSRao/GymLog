from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.db.models import Exercise, ExerciseDef, Workout
from app.workouts.schemas import (
    ImportError,
    ImportResponse,
    WorkoutRequest,
)


def build_workout_detailed(db: Session, session: Workout) -> dict:
    """Build the detailed workout dict used by WorkoutDetailed."""
    sets = (
        db.query(Exercise)
        .options(
            joinedload(Exercise.exercise_def).joinedload(
                ExerciseDef.muscle_groups
            )
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


def log_workout(
    db: Session, workout: WorkoutRequest, user_id: int
) -> Workout:
    """Persist a new workout session for user_id with all its sets."""
    session = (
        Workout(
            raw_input=workout.notes,
            logged_at=workout.logged_at,
            user_id=user_id,
        )
        if workout.logged_at
        else Workout(raw_input=workout.notes, user_id=user_id)
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


def get_workout(
    db: Session, session_id: int, user_id: int
) -> Workout | None:
    """Return a workout session owned by user_id, or None if not found."""
    return (
        db.query(Workout)
        .filter(Workout.id == session_id, Workout.user_id == user_id)
        .first()
    )


def get_all_workouts(
    db: Session,
    user_id: int,
    year: int | None = None,
    month: int | None = None,
) -> list[Workout]:
    """Return workout sessions for user_id, optionally filtered to one month."""
    q = db.query(Workout).filter(Workout.user_id == user_id)
    if year is not None and month is not None:
        start = datetime(year, month, 1)
        end = (
            datetime(year + 1, 1, 1)
            if month == 12
            else datetime(year, month + 1, 1)
        )
        q = q.filter(Workout.logged_at >= start, Workout.logged_at < end)
    return q.order_by(Workout.logged_at.desc()).all()


def update_workout(
    db: Session,
    session_id: int,
    workout: WorkoutRequest,
    user_id: int,
) -> Workout | None:
    """Replace all sets in a workout owned by user_id; returns None if not found."""
    session = (
        db.query(Workout)
        .filter(Workout.id == session_id, Workout.user_id == user_id)
        .first()
    )
    if not session:
        return None

    session.raw_input = workout.notes
    if workout.logged_at:
        session.logged_at = workout.logged_at
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


def delete_workout(
    db: Session, session_id: int, user_id: int
) -> bool:
    """Delete a workout owned by user_id; returns False if not found."""
    session = (
        db.query(Workout)
        .filter(Workout.id == session_id, Workout.user_id == user_id)
        .first()
    )
    if not session:
        return False
    db.delete(session)
    db.commit()
    return True


def import_workouts(
    db: Session,
    sessions: list,
    user_id: int,
) -> ImportResponse:
    """Bulk-insert workout sessions; skip invalid ones and report errors."""
    all_exercise_ids: set[int] = {
        e.exercise_id
        for s in sessions
        for e in s.exercises
    }
    valid_ids: set[int] = {
        row[0]
        for row in db.query(ExerciseDef.id)
        .filter(ExerciseDef.id.in_(all_exercise_ids))
        .all()
    }

    sessions_created = 0
    sets_created = 0
    errors: list[ImportError] = []

    for i, s in enumerate(sessions):
        invalid = [
            e.exercise_id
            for e in s.exercises
            if e.exercise_id not in valid_ids
        ]
        if invalid:
            errors.append(
                ImportError(
                    index=i,
                    reason=f"exercise_id {invalid[0]} does not exist",
                )
            )
            continue

        workout = Workout(logged_at=s.logged_at, user_id=user_id)
        db.add(workout)
        db.flush()

        for exercise in s.exercises:
            for j, ex_set in enumerate(exercise.sets):
                db.add(Exercise(
                    session_id=workout.id,
                    exercise_id=exercise.exercise_id,
                    set_number=j + 1,
                    reps=ex_set.reps,
                    weight_lbs=ex_set.weight_lbs,
                ))
                sets_created += 1

        sessions_created += 1

    db.commit()
    return ImportResponse(
        sessions_created=sessions_created,
        sets_created=sets_created,
        errors=errors,
    )
