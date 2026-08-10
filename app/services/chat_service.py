import json
import os
from datetime import datetime, timedelta, timezone
from typing import Generator

from openai import OpenAI
from sqlalchemy.orm import Session

from app.api.schemas import ExerciseLogRequest, SetSchema, WorkoutRequest
from app.services.exercise_service import (
    get_all_exercises,
    get_exercise_progression,
)
from app.services.workout_service import (
    get_all_workouts,
    log_workout as _log_workout,
)

_client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
)

_MODEL = "llama-3.3-70b-versatile"

_SYSTEM = (
    "You are GymBot, an AI assistant built into GymLog, a personal workout"
    " tracker. You can help the user log workouts, review history, check"
    " progression on specific exercises, and search exercises by name."
    " When the user wants to log a workout, confirm the details first, then"
    " call log_workout. Be concise and friendly. Use specific numbers when"
    " reporting data."
)

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_exercises",
            "description": (
                "Search exercises by name or keyword. Returns matching"
                " exercise names and IDs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term, e.g. 'bench press'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_workouts",
            "description": "Get the user's recent workout sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back",
                    }
                },
                "required": ["days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exercise_progression",
            "description": (
                "Get progression history (sets, volume, best weight) for"
                " a specific exercise by name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "exercise_name": {
                        "type": "string",
                        "description": "Name of the exercise",
                    }
                },
                "required": ["exercise_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_workout",
            "description": (
                "Log a new workout session with exercises, sets, reps,"
                " and weights. Only call after confirming details with user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "exercises": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "exercise_name": {"type": "string"},
                                "sets": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "reps": {"type": "integer"},
                                            "weight_lbs": {
                                                "type": "number",
                                                "description": (
                                                    "Weight in lbs;"
                                                    " omit for bodyweight"
                                                ),
                                            },
                                        },
                                        "required": ["reps"],
                                    },
                                },
                            },
                            "required": ["exercise_name", "sets"],
                        },
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes for the workout",
                    },
                },
                "required": ["exercises"],
            },
        },
    },
]


def _execute_tool(name: str, arguments: str, db: Session) -> str:
    """Execute a tool call and return its result as a JSON string."""
    inputs = json.loads(arguments)

    if name == "search_exercises":
        query = inputs["query"].lower()
        exercises = get_all_exercises(db)
        matches = [
            {"id": e.id, "name": e.name, "equipment": e.equipment}
            for e in exercises
            if query in e.name.lower()
        ][:20]
        return json.dumps({"matches": matches, "count": len(matches)})

    if name == "get_recent_workouts":
        days = inputs.get("days", 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        workouts = get_all_workouts(db)
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

    if name == "get_exercise_progression":
        exercise_name = inputs["exercise_name"].lower()
        all_ex = get_all_exercises(db)
        match = next(
            (e for e in all_ex if exercise_name in e.name.lower()), None
        )
        if not match:
            return json.dumps({
                "error": (
                    f"No exercise found matching '{inputs['exercise_name']}'."
                    " Try search_exercises first."
                )
            })
        _, sessions = get_exercise_progression(db, match.id)
        return json.dumps({
            "exercise": match.name,
            "sessions": [
                {
                    "date": s["logged_at"].strftime("%Y-%m-%d"),
                    "sets": s["sets"],
                    "volume": s["volume"],
                    "best_set_weight": s["best_set_weight"],
                }
                for s in sessions[-10:]
            ],
        })

    if name == "log_workout":
        all_ex = get_all_exercises(db)
        ex_by_name = {e.name.lower(): e for e in all_ex}

        logged_exercises = []
        not_found = []
        for ex in inputs["exercises"]:
            name_lower = ex["exercise_name"].lower()
            match = ex_by_name.get(name_lower) or next(
                (e for e in all_ex if name_lower in e.name.lower()), None
            )
            if not match:
                not_found.append(ex["exercise_name"])
                continue
            sets = [
                SetSchema(reps=s["reps"], weight_lbs=s.get("weight_lbs"))
                for s in ex["sets"]
            ]
            logged_exercises.append(
                ExerciseLogRequest(exercise_id=match.id, sets=sets)
            )

        if not_found:
            return json.dumps({
                "error": (
                    f"Exercises not found: {', '.join(not_found)}."
                    " Use search_exercises to find exact names."
                )
            })

        req = WorkoutRequest(
            exercises=logged_exercises,
            notes=inputs.get("notes"),
        )
        session = _log_workout(db, req)
        return json.dumps({
            "success": True,
            "session_id": session.id,
            "logged_at": session.logged_at.isoformat(),
            "exercises_logged": len(logged_exercises),
        })

    return json.dumps({"error": f"Unknown tool: {name}"})


def run_chat(
    db: Session, messages: list[dict]
) -> Generator[str, None, None]:
    """Run the agentic tool loop; yield text chunks for SSE streaming."""
    loop_messages = [{"role": "system", "content": _SYSTEM}] + list(messages)

    while True:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=loop_messages,
            tools=_TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]

        if choice.finish_reason != "tool_calls":
            yield choice.message.content or ""
            break

        # Append assistant message with tool_calls
        loop_messages.append(choice.message)

        # Execute each tool and append results
        for tc in choice.message.tool_calls:
            result = _execute_tool(tc.function.name, tc.function.arguments, db)
            loop_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
