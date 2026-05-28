from sqlalchemy.orm import Session
from app.model.models import Workout, Exercise
from app.api.schemas import WorkoutRequest
from typing import Optional


def log_workout(db: Session, workout: WorkoutRequest) -> Workout:
    session = Workout()
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


def get_workout(db: Session, session_id: int) -> Optional[Workout]:
    return db.query(Workout).filter(Workout.id == session_id).first()


def get_all_workouts(db: Session) -> list[Workout]:
    return db.query(Workout).order_by(Workout.logged_at.desc()).all()


def update_workout(db: Session, session_id: int, workout: WorkoutRequest) -> Optional[Workout]:
    session = db.query(Workout).filter(Workout.id == session_id).first()
    if not session:
        return None

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
    session = db.query(Workout).filter(Workout.id == session_id).first()
    if not session:
        return False
    db.delete(session)
    db.commit()
    return True
