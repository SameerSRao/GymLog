import json
from datetime import datetime, timedelta, timezone

from google.genai import types
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import ExerciseLogRequest, SetSchema, WorkoutRequest
from app.model.models import ExerciseDef, Routine, RoutineExercise
from app.services.exercise_service import get_exercise_progression
from app.services.workout_service import (
    get_all_workouts,
    log_workout as _log_workout,
)

TOOLS = types.Tool(
    function_declarations=[
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
            name="get_routines",
            description=(
                "List all saved workout routines with their exercises."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
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
    ]
)


def _all_exercises_with_muscles(db: Session) -> list[ExerciseDef]:
    """Return all exercises with muscle groups eager-loaded."""
    return (
        db.query(ExerciseDef)
        .options(joinedload(ExerciseDef.muscle_groups))
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


def execute_tool(name: str, inputs: dict, db: Session) -> str:
    """Dispatch a tool call by name and return the result as a JSON string."""
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
            _, sessions = get_exercise_progression(db, candidate.id)
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

    if name == "get_routines":
        routines = (
            db.query(Routine)
            .options(
                joinedload(Routine.exercises).joinedload(
                    RoutineExercise.exercise_def
                )
            )
            .order_by(Routine.name)
            .all()
        )
        result = [
            {
                "id": r.id,
                "name": r.name,
                "exercises": [
                    {
                        "position": ex.position,
                        "name": ex.exercise_def.name,
                        "sets": ex.num_sets,
                    }
                    for ex in sorted(r.exercises, key=lambda x: x.position)
                ],
            }
            for r in routines
        ]
        return json.dumps({"routines": result, "count": len(result)})

    if name == "log_workout":
        all_ex = _all_exercises_with_muscles(db)
        ex_by_name = {e.name.lower(): e for e in all_ex}

        logged_exercises = []
        not_found = []
        for ex in inputs["exercises"]:
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
            logged_exercises.append(
                ExerciseLogRequest(exercise_id=match.id, sets=sets)
            )

        if not_found:
            return json.dumps({
                "error": (
                    f"Exercises not found: {', '.join(not_found)}."
                    " Use search_exercises to find the correct name."
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
