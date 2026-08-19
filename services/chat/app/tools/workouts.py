import json
from datetime import datetime, timedelta, timezone

from google.genai import types

from app.client.api_client import api_client
from app.tools.base import _not_found_error, _resolve_exercise_names

WORKOUT_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_recent_workouts",
        description="Get the user's recent workout sessions.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "days": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of days to look back",
                )
            },
            required=["days"],
        ),
    ),
    types.FunctionDeclaration(
        name="log_workout",
        description=(
            "Log a new workout session. Only call after the user has"
            " explicitly confirmed the exercise list, sets, reps,"
            " and weights."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "exercises": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "exercise_name": types.Schema(
                                type=types.Type.STRING
                            ),
                            "sets": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "reps": types.Schema(
                                            type=types.Type.INTEGER
                                        ),
                                        "weight_lbs": types.Schema(
                                            type=types.Type.NUMBER,
                                            description=(
                                                "Weight in lbs;"
                                                " omit for bodyweight"
                                            ),
                                        ),
                                    },
                                    required=["reps"],
                                ),
                            ),
                        },
                        required=["exercise_name", "sets"],
                    ),
                ),
                "notes": types.Schema(
                    type=types.Type.STRING,
                    description="Optional notes for the workout",
                ),
                "logged_at": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "ISO 8601 datetime for when the workout occurred"
                        " (e.g. '2024-03-15T14:30:00'). Omit to use the"
                        " user's current local time."
                    ),
                ),
            },
            required=["exercises"],
        ),
    ),
    types.FunctionDeclaration(
        name="delete_workout",
        description=(
            "Delete a workout session by session_id. Call"
            " get_recent_workouts first to find the correct session_id."
            " Only call after the user has explicitly confirmed."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "session_id": types.Schema(
                    type=types.Type.INTEGER,
                    description="The session ID to delete",
                ),
            },
            required=["session_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_workout",
        description=(
            "Replace all exercises and sets in an existing workout"
            " session in-place. Call get_recent_workouts first to find"
            " the session_id. Only call after the user has explicitly"
            " confirmed the full updated exercise list."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "session_id": types.Schema(
                    type=types.Type.INTEGER,
                    description="The session ID to update",
                ),
                "exercises": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "exercise_name": types.Schema(
                                type=types.Type.STRING
                            ),
                            "sets": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "reps": types.Schema(
                                            type=types.Type.INTEGER
                                        ),
                                        "weight_lbs": types.Schema(
                                            type=types.Type.NUMBER,
                                            description=(
                                                "Weight in lbs;"
                                                " omit for bodyweight"
                                            ),
                                        ),
                                    },
                                    required=["reps"],
                                ),
                            ),
                        },
                        required=["exercise_name", "sets"],
                    ),
                ),
                "notes": types.Schema(type=types.Type.STRING),
            },
            required=["session_id", "exercises"],
        ),
    ),
]


def _build_workout_exercises(
    exercise_inputs: list[dict],
    ex_by_name: dict[str, dict],
    all_ex: list[dict],
) -> tuple[list[dict], list[str]]:
    """Resolve exercise inputs to workout log dicts.

    Returns (exercise_log_dicts, not_found_names).
    Each exercise_log_dict has keys: exercise_id, sets.
    """
    pairs, not_found = _resolve_exercise_names(
        exercise_inputs, ex_by_name, all_ex
    )
    logged = [
        {
            "exercise_id": ex["id"],
            "sets": [
                {"reps": s["reps"], "weight_lbs": s.get("weight_lbs")}
                for s in inp["sets"]
            ],
        }
        for inp, ex in pairs
    ]
    return logged, not_found


def handle_workout_tool(
    name: str,
    inputs: dict,
    token: str,
    local_time: str | None = None,
) -> str:
    """Dispatch a workout tool call; return result as a JSON string."""
    if name == "get_recent_workouts":
        days = inputs.get("days", 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        workouts = api_client.get_workouts(token)
        recent = []
        for w in workouts:
            logged_str = w["logged_at"]
            logged = datetime.fromisoformat(logged_str)
            if logged.tzinfo is None:
                logged = logged.replace(tzinfo=timezone.utc)
            if logged < cutoff:
                continue
            detail = api_client.get_workout(token, w["session_id"])
            exercises_done = list(
                {ex["name"] for ex in detail.get("exercises", [])}
            )
            recent.append({
                "session_id": w["session_id"],
                "date": logged.strftime("%Y-%m-%d"),
                "exercises": exercises_done,
                "total_sets": w["sets_logged"],
            })
        return json.dumps({"workouts": recent, "count": len(recent)})

    if name == "log_workout":
        all_ex = api_client.get_exercises(token)
        ex_by_name = {e["name"].lower(): e for e in all_ex}
        logged, not_found = _build_workout_exercises(
            inputs["exercises"], ex_by_name, all_ex
        )
        if not_found:
            return _not_found_error(not_found)
        raw_ts = inputs.get("logged_at") or local_time
        logged_at = None
        if raw_ts:
            try:
                logged_at = datetime.fromisoformat(raw_ts).isoformat()
            except ValueError:
                pass
        data = {"exercises": logged, "notes": inputs.get("notes")}
        if logged_at:
            data["logged_at"] = logged_at
        try:
            result = api_client.post_workout(token, data)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({
            "success": True,
            "session_id": result["session_id"],
            "logged_at": result["logged_at"],
            "exercises_logged": result["exercises_logged"],
        })

    if name == "delete_workout":
        session_id = inputs["session_id"]
        try:
            found = api_client.delete_workout(token, session_id)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        if not found:
            return json.dumps({
                "error": f"Workout session {session_id} not found."
            })
        return json.dumps({
            "success": True,
            "deleted_session_id": session_id,
        })

    if name == "update_workout":
        session_id = inputs["session_id"]
        all_ex = api_client.get_exercises(token)
        ex_by_name = {e["name"].lower(): e for e in all_ex}
        logged, not_found = _build_workout_exercises(
            inputs["exercises"], ex_by_name, all_ex
        )
        if not_found:
            return _not_found_error(not_found)
        data = {"exercises": logged, "notes": inputs.get("notes")}
        try:
            result = api_client.put_workout(token, session_id, data)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({
            "success": True,
            "session_id": result["session_id"],
            "exercises_updated": result["exercises_logged"],
        })

    return json.dumps({"error": f"Unknown workout tool: {name}"})
