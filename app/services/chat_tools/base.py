from sqlalchemy.orm import Session, joinedload

from app.model.models import ExerciseDef, MuscleGroup, Routine


def _all_exercises_with_muscles(
    db: Session, user_id: int
) -> list[ExerciseDef]:
    """Return exercises visible to user_id with muscle groups eager-loaded."""
    return (
        db.query(ExerciseDef)
        .options(joinedload(ExerciseDef.muscle_groups))
        .filter(
            (ExerciseDef.user_id.is_(None))
            | (ExerciseDef.user_id == user_id)
        )
        .order_by(ExerciseDef.name)
        .all()
    )


def _best_exercise_match(
    query_words: list[str], exercises: list[ExerciseDef]
) -> ExerciseDef | None:
    """Return the best word-level match, falling back to substring match."""
    q_set = set(query_words)
    word_matches = [
        e for e in exercises
        if q_set.issubset(set(e.name.lower().split()))
    ]
    if word_matches:
        return word_matches[0]
    query_str = " ".join(query_words)
    sub_matches = [e for e in exercises if query_str in e.name.lower()]
    return sub_matches[0] if sub_matches else None


def _resolve_routine(
    name: str, db: Session, user_id: int
) -> Routine | dict:
    """Return matching Routine (with exercises loaded) or an error dict.

    Returns an error dict if zero or multiple routines match the name.
    """
    q = name.lower()
    routines = (
        db.query(Routine)
        .options(joinedload(Routine.exercises))
        .filter(Routine.user_id == user_id)
        .all()
    )
    matches = [r for r in routines if q in r.name.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return {
            "error": (
                f"Multiple routines match '{name}': "
                f"{[r.name for r in matches]}. Be more specific."
            )
        }
    names = [r.name for r in routines]
    return {
        "error": (
            f"No routine found matching '{name}'. "
            f"Your routines: {names}"
        )
    }


def _resolve_muscle_groups(
    names: list[str], db: Session
) -> tuple[list[int], list[str]]:
    """Resolve muscle group name strings to IDs.

    Returns (matched_ids, unresolved_names).
    """
    all_mgs = db.query(MuscleGroup).all()
    matched_ids: list[int] = []
    unresolved: list[str] = []
    for name in names:
        q = name.lower()
        match = next(
            (mg for mg in all_mgs if q in mg.name.lower()), None
        )
        if match:
            matched_ids.append(match.id)
        else:
            unresolved.append(name)
    return matched_ids, unresolved
