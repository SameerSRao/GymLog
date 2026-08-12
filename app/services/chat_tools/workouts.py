import json
from datetime import datetime, timedelta, timezone

from google.genai import types
from sqlalchemy.orm import Session

from app.api.schemas import ExerciseLogRequest, SetSchema, WorkoutRequest
from app.model.models import ExerciseDef
from app.services.chat_tools.base import (
    _all_exercises_with_muscles,
    _best_exercise_match,
)
from app.services.workout_service import (
    delete_workout as _delete_workout,
    get_all_workouts,
    log_workout as _log_workout,
    update_workout as _update_workout,
)

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


def _resolve_exercise_inputs(
    exercise_inputs: list[dict],
    ex_by_name: dict[str, ExerciseDef],
    all_ex: list[ExerciseDef],
) -> tuple[list[ExerciseLogRequest], list[str]]:
    """Resolve exercise name dicts to ExerciseLogRequests.

    Returns (requests, not_found_names).
    """
    logged: list[ExerciseLogRequest] = []
    not_found: list[str] = []
    for ex in exercise_inputs:
        name_lower = ex["exercise_name"].lower()
        match = ex_by_name.get(name_lower) or _best_exercise_match(
            name_lower.split(), all_ex
        )
        if not match:
            not_found.append(ex["exercise_name"])
            continue
        sets = [
            SetSchema(reps=s["reps"], weight_lbs=s.get("weight_lbs"))
            for s in ex["sets"]
        ]
        logged.append(ExerciseLogRequest(exercise_id=match.id, sets=sets))
    return logged, not_found


def handle_workout_tool(
    name: str, inputs: dict, db: Session, user_id: int
) -> str:
    """Dispatch a workout tool call; return result as a JSON string."""
    if name == "get_recent_workouts":
        days = inputs.get("days", 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        workouts = get_all_workouts(db, user_id)
        recent = []
        for w in workouts:
            logged = w.logged_at
            if logged.tzinfo is None:
                logged = logged.replace(tzinfo=timezone.utc)
            if logged < cutoff:
                continue
            exercises_done = list({s.exercise_def.name for s in w.sets})
            recent.append({
                "session_id": w.id,
                "date": w.logged_at.strftime("%Y-%m-%d"),
                "exercises": exercises_done,
                "total_sets": len(w.sets),
            })
        return json.dumps({"workouts": recent, "count": len(recent)})

    if name == "log_workout":
        all_ex = _all_exercises_with_muscles(db)
        ex_by_name = {e.name.lower(): e for e in all_ex}
        logged, not_found = _resolve_exercise_inputs(
            inputs["exercises"], ex_by_name, all_ex
        )
        if not_found:
            return json.dumps({
                "error": (
                    f"Exercises not found: {', '.join(not_found)}."
                    " Use search_exercises to find the correct name."
                )
            })
        req = WorkoutRequest(
            exercises=logged, notes=inputs.get("notes")
        )
        session = _log_workout(db, req, user_id)
        return json.dumps({
            "success": True,
            "session_id": session.id,
            "logged_at": session.logged_at.isoformat(),
            "exercises_logged": len(logged),
        })

    if name == "delete_workout":
        session_id = inputs["session_id"]
        found = _delete_workout(db, session_id, user_id)
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
        all_ex = _all_exercises_with_muscles(db)
        ex_by_name = {e.name.lower(): e for e in all_ex}
        logged, not_found = _resolve_exercise_inputs(
            inputs["exercises"], ex_by_name, all_ex
        )
        if not_found:
            return json.dumps({
                "error": (
                    f"Exercises not found: {', '.join(not_found)}."
                    " Use search_exercises to find the correct name."
                )
            })
        req = WorkoutRequest(
            exercises=logged, notes=inputs.get("notes")
        )
        session = _update_workout(db, session_id, req, user_id)
        if not session:
            return json.dumps({
                "error": f"Workout session {session_id} not found."
            })
        return json.dumps({
            "success": True,
            "session_id": session.id,
            "exercises_updated": len(logged),
        })

    return json.dumps({"error": f"Unknown workout tool: {name}"})
