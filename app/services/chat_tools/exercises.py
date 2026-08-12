import json

from google.genai import types
from sqlalchemy.orm import Session

from app.services.chat_tools.base import _all_exercises_with_muscles
from app.services.exercise_service import get_exercise_progression

EXERCISE_DECLARATIONS = [
    types.FunctionDeclaration(
        name="search_exercises",
        description=(
            "Search exercises by name or muscle group keyword."
            " Returns matching exercise names, IDs, equipment,"
            " and muscle groups."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Search term — a muscle group (e.g. 'chest',"
                        " 'back') or exercise name (e.g. 'bench press')"
                    ),
                )
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_exercise_progression",
        description=(
            "Get progression history (sets, volume, best weight)"
            " for a specific exercise. Prefers exercises the user"
            " has actually logged."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "exercise_name": types.Schema(
                    type=types.Type.STRING,
                    description="Name of the exercise",
                )
            },
            required=["exercise_name"],
        ),
    ),
]


def handle_exercise_tool(
    name: str, inputs: dict, db: Session, user_id: int
) -> str:
    """Dispatch an exercise tool call; return result as a JSON string."""
    if name == "search_exercises":
        query = inputs["query"].lower()
        exercises = _all_exercises_with_muscles(db)
        matches = [
            {
                "id": e.id,
                "name": e.name,
                "equipment": e.equipment,
                "muscle_groups": [mg.name for mg in e.muscle_groups],
            }
            for e in exercises
            if query in e.name.lower()
            or any(query in mg.name.lower() for mg in e.muscle_groups)
        ][:20]
        return json.dumps({"matches": matches, "count": len(matches)})

    if name == "get_exercise_progression":
        raw_name = inputs["exercise_name"]
        query_words = raw_name.lower().split()
        exercises = _all_exercises_with_muscles(db)
        q_set = set(query_words)
        candidates = [
            e for e in exercises
            if q_set.issubset(set(e.name.lower().split()))
        ]
        if not candidates:
            candidates = [
                e for e in exercises
                if " ".join(query_words) in e.name.lower()
            ]
        if not candidates:
            return json.dumps({
                "error": (
                    f"No exercise found matching '{raw_name}'."
                    " Try search_exercises to find the correct name."
                )
            })
        best = None
        best_sessions: list = []
        for candidate in candidates[:5]:
            _, sessions = get_exercise_progression(
                db, candidate.id, user_id
            )
            if len(sessions) > len(best_sessions):
                best = candidate
                best_sessions = sessions
        if not best or not best_sessions:
            names = ", ".join(c.name for c in candidates[:5])
            return json.dumps({
                "error": (
                    f"No logged data found for '{raw_name}'."
                    f" Matching exercises: {names}."
                    " Have you logged any of these?"
                )
            })
        return json.dumps({
            "exercise": best.name,
            "sessions": [
                {
                    "date": s["logged_at"].strftime("%Y-%m-%d"),
                    "sets": s["sets"],
                    "volume": s["volume"],
                    "best_set_weight": s["best_set_weight"],
                }
                for s in best_sessions[-10:]
            ],
        })

    return json.dumps({"error": f"Unknown exercise tool: {name}"})
