import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.model.models import ExerciseDef, MuscleGroup

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
    return _ALIASES.get(name, name)


def seed_exercises(db: Session) -> None:
    if db.query(ExerciseDef).count() > 0:
        return

    with open(_EXERCISES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Collect canonical muscle names (aliases already collapsed)
    all_muscles: set[str] = set()
    for ex in data:
        for m in [ex.get("target"), ex.get("muscle_group")] + ex.get("secondary_muscles", []):
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
        for m in [ex.get("target"), ex.get("muscle_group")] + ex.get("secondary_muscles", []):
            if not m:
                continue
            canonical = _canonical(m)
            if canonical not in seen_muscles and canonical in mg_map:
                muscles.append(mg_map[canonical])
                seen_muscles.add(canonical)

        instructions_raw = ex.get("instructions", {})
        instructions = instructions_raw.get("en") if isinstance(instructions_raw, dict) else None

        db.add(ExerciseDef(
            name=ex["name"],
            equipment=ex.get("equipment"),
            target=ex.get("target"),
            instructions=instructions,
            muscle_groups=muscles,
        ))

    db.commit()
