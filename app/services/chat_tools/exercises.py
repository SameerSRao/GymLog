import json

from google.genai import types
from sqlalchemy.orm import Session

from app.api.schemas import CreateExerciseSchema, ExerciseUpdate
from app.services.chat_tools.base import (
    _all_exercises_with_muscles,
    _best_exercise_match,
    _resolve_muscle_groups,
)
from app.services.exercise_service import (
    create_exercise as _create_exercise,
    delete_exercise as _delete_exercise,
    get_exercise_progression,
    update_exercise as _update_exercise,
)

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
    types.FunctionDeclaration(
        name="create_exercise",
        description=(
            "Create a custom exercise for the user. Only call after"
            " the user has confirmed the name, equipment, and muscle"
            " groups."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(type=types.Type.STRING),
                "equipment": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Equipment type (e.g. 'barbell', 'dumbbell');"
                        " omit if bodyweight"
                    ),
                ),
                "muscle_group_names": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description=(
                        "Muscle group names (e.g. ['chest', 'triceps'])"
                    ),
                ),
            },
            required=["name", "muscle_group_names"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_exercise",
        description=(
            "Edit a custom exercise the user owns. Only call after the"
            " user has confirmed the changes."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "exercise_name": types.Schema(
                    type=types.Type.STRING,
                    description="Current name of the exercise to edit",
                ),
                "new_name": types.Schema(type=types.Type.STRING),
                "equipment": types.Schema(type=types.Type.STRING),
                "muscle_group_names": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
            },
            required=["exercise_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="delete_exercise",
        description=(
            "Delete a custom exercise the user owns. Only call after"
            " the user has explicitly confirmed."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "exercise_name": types.Schema(type=types.Type.STRING),
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
        exercises = _all_exercises_with_muscles(db, user_id)
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
        exercises = _all_exercises_with_muscles(db, user_id)
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

    if name == "create_exercise":
        mg_names = inputs.get("muscle_group_names", [])
        mg_ids, unresolved = _resolve_muscle_groups(mg_names, db)
        if unresolved:
            return json.dumps({
                "error": (
                    f"Unknown muscle groups: {unresolved}."
                    " Try search_exercises to find valid muscle group"
                    " names."
                )
            })
        data = CreateExerciseSchema(
            name=inputs["name"],
            equipment=inputs.get("equipment"),
            instructions=None,
            muscle_group_ids=mg_ids,
        )
        ex = _create_exercise(db, data, user_id)
        return json.dumps({
            "success": True,
            "exercise_id": ex.id,
            "name": ex.name,
        })

    if name == "update_exercise":
        raw_name = inputs["exercise_name"]
        exercises = _all_exercises_with_muscles(db, user_id)
        ex_by_name = {e.name.lower(): e for e in exercises}
        match = ex_by_name.get(raw_name.lower()) or _best_exercise_match(
            raw_name.lower().split(), exercises
        )
        if not match:
            return json.dumps({
                "error": (
                    f"No exercise found matching '{raw_name}'."
                    " Use search_exercises to find the correct name."
                )
            })
        mg_ids = None
        if inputs.get("muscle_group_names"):
            mg_ids, unresolved = _resolve_muscle_groups(
                inputs["muscle_group_names"], db
            )
            if unresolved:
                return json.dumps({
                    "error": f"Unknown muscle groups: {unresolved}."
                })
        data = ExerciseUpdate(
            name=inputs.get("new_name"),
            equipment=inputs.get("equipment"),
            muscle_group_ids=mg_ids,
        )
        try:
            updated = _update_exercise(
                db, match.id, data, user_id=user_id, is_admin=False
            )
        except ValueError as e:
            if str(e) == "forbidden":
                return json.dumps({
                    "error": (
                        f"You don't have permission to edit"
                        f" '{match.name}'. You can only edit exercises"
                        " you created."
                    )
                })
            if str(e) == "name_conflict":
                return json.dumps({
                    "error": (
                        f"An exercise named '{inputs.get('new_name')}'"
                        " already exists."
                    )
                })
            raise
        if not updated:
            return json.dumps({"error": "Exercise not found."})
        return json.dumps({
            "success": True,
            "exercise_id": updated.id,
            "name": updated.name,
        })

    if name == "delete_exercise":
        raw_name = inputs["exercise_name"]
        exercises = _all_exercises_with_muscles(db, user_id)
        ex_by_name = {e.name.lower(): e for e in exercises}
        match = ex_by_name.get(raw_name.lower()) or _best_exercise_match(
            raw_name.lower().split(), exercises
        )
        if not match:
            return json.dumps({
                "error": f"No exercise found matching '{raw_name}'."
            })
        try:
            found = _delete_exercise(
                db, match.id, user_id=user_id, is_admin=False
            )
        except ValueError as e:
            if str(e) == "forbidden":
                return json.dumps({
                    "error": (
                        f"You don't have permission to delete"
                        f" '{match.name}'. You can only delete exercises"
                        " you created."
                    )
                })
            if str(e) == "has_history":
                return json.dumps({
                    "error": (
                        f"'{match.name}' has logged workout history"
                        " and cannot be deleted."
                    )
                })
            raise
        if not found:
            return json.dumps({"error": "Exercise not found."})
        return json.dumps({"success": True, "deleted": match.name})

    return json.dumps({"error": f"Unknown exercise tool: {name}"})
