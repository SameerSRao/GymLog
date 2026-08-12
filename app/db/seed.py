import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.model.models import Exercise, ExerciseDef, MuscleGroup, User, Workout
from app.services.auth_service import hash_password

_EXERCISES_FILE = Path(__file__).parent.parent.parent / "exercises.json"

# Canonical name wins; all aliases map to it
_ALIASES: dict[str, str] = {
    "abdominals": "abs",
    "deltoids": "delts",
    "latissimus dorsi": "lats",
    "quadriceps": "quads",
    "trapezius": "traps",
}


def _canonical(name: str) -> str:
    """Return the canonical muscle group name, collapsing known aliases."""
    return _ALIASES.get(name, name)


def seed_exercises(db: Session) -> None:
    """Populate the database with exercises from exercises.json; no-op if already seeded."""
    if db.query(ExerciseDef).count() > 0:
        return

    with open(_EXERCISES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Collect canonical muscle names (aliases already collapsed)
    all_muscles: set[str] = set()
    for ex in data:
        for m in (
            [ex.get("target"), ex.get("muscle_group")]
            + ex.get("secondary_muscles", [])
        ):
            if m:
                all_muscles.add(_canonical(m))

    mg_map: dict[str, MuscleGroup] = {}
    for name in sorted(all_muscles):
        mg = MuscleGroup(name=name)
        db.add(mg)
        mg_map[name] = mg
    db.flush()

    seen: set[str] = set()
    for ex in data:
        key = ex["name"].lower().strip()
        if key in seen:
            continue
        seen.add(key)

        muscles: list[MuscleGroup] = []
        seen_muscles: set[str] = set()
        for m in (
            [ex.get("target"), ex.get("muscle_group")]
            + ex.get("secondary_muscles", [])
        ):
            if not m:
                continue
            canonical = _canonical(m)
            if canonical not in seen_muscles and canonical in mg_map:
                muscles.append(mg_map[canonical])
                seen_muscles.add(canonical)

        instructions_raw = ex.get("instructions", {})
        instructions = (
            instructions_raw.get("en")
            if isinstance(instructions_raw, dict)
            else None
        )

        db.add(ExerciseDef(
            name=ex["name"],
            equipment=ex.get("equipment"),
            instructions=instructions,
            muscle_groups=muscles,
        ))

    db.commit()


def seed_demo_data(db: Session) -> None:
    """Create demo user and refresh workout data when stale (>30 days old)."""
    demo = db.query(User).filter(User.username == "demo").first()
    if not demo:
        demo = User(
            username="demo",
            password_hash=hash_password("demo-no-login"),
            is_demo=True,
        )
        db.add(demo)
        db.commit()
        db.refresh(demo)

    now = datetime.now(timezone.utc)
    newest = (
        db.query(Workout)
        .filter(Workout.user_id == demo.id)
        .order_by(Workout.logged_at.desc())
        .first()
    )

    if newest is not None:
        newest_dt = newest.logged_at
        if newest_dt.tzinfo is None:
            newest_dt = newest_dt.replace(tzinfo=timezone.utc)
        if (now - newest_dt).days < 30:
            return

    db.query(Workout).filter(Workout.user_id == demo.id).delete()
    db.commit()

    exercises = (
        db.query(ExerciseDef)
        .filter(ExerciseDef.user_id.is_(None))
        .limit(5)
        .all()
    )
    if not exercises:
        return

    ex_ids = [e.id for e in exercises]
    for week in range(8):
        for day_offset in [1, 3, 5]:
            days_ago = (7 * week) + day_offset
            workout_date = now - timedelta(days=days_ago)
            session = Workout(
                logged_at=workout_date,
                user_id=demo.id,
            )
            db.add(session)
            db.flush()

            for ex_id in ex_ids[:2]:
                base_weight = float(100 + (week * 5))
                for set_num in range(1, 4):
                    db.add(Exercise(
                        session_id=session.id,
                        exercise_id=ex_id,
                        set_number=set_num,
                        reps=5,
                        weight_lbs=base_weight,
                    ))

    db.commit()
