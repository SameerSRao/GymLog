import json

from google.genai import types
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import (
    RoutineCreate,
    RoutineExerciseRequest,
    RoutineUpdate,
)
from app.model.models import Routine, RoutineExercise
from app.services.chat_tools.base import (
    _all_exercises_with_muscles,
    _best_exercise_match,
    _resolve_routine,
)
from app.services.routine_service import (
    create_routine as _create_routine,
    delete_routine as _delete_routine,
    update_routine as _update_routine,
)


def _resolve_routine_exercises(
    exercise_inputs: list[dict],
    ex_by_name: dict,
    all_ex: list,
) -> tuple[list[RoutineExerciseRequest], list[str]]:
    """Resolve exercise name dicts to RoutineExerciseRequests.

    Returns (requests, not_found_names).
    """
    requests: list[RoutineExerciseRequest] = []
    not_found: list[str] = []
    for i, ex in enumerate(exercise_inputs):
        name_lower = ex["exercise_name"].lower()
        match = ex_by_name.get(name_lower) or _best_exercise_match(
            name_lower.split(), all_ex
        )
        if not match:
            not_found.append(ex["exercise_name"])
            continue
        requests.append(
            RoutineExerciseRequest(
                exercise_id=match.id,
                position=i + 1,
                num_sets=ex["sets"],
            )
        )
    return requests, not_found


ROUTINE_DECLARATIONS = [
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
        name="create_routine",
        description=(
            "Create a new workout routine. Only call after the user"
            " has confirmed the name and exercise list."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(
                    type=types.Type.STRING,
                    description="Name for the new routine",
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
                                type=types.Type.INTEGER,
                                description="Default number of sets",
                            ),
                        },
                        required=["exercise_name", "sets"],
                    ),
                ),
            },
            required=["name", "exercises"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_routine",
        description=(
            "Replace a routine's name and/or exercise list. Only call"
            " after the user has confirmed the full updated routine."
            " Omit 'exercises' to keep the current list unchanged."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "routine_name": types.Schema(
                    type=types.Type.STRING,
                    description="Current name of the routine to update",
                ),
                "new_name": types.Schema(
                    type=types.Type.STRING,
                    description="New name; omit to keep the current name",
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
                                type=types.Type.INTEGER
                            ),
                        },
                        required=["exercise_name", "sets"],
                    ),
                ),
            },
            required=["routine_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="delete_routine",
        description=(
            "Delete a routine by name. Only call after the user has"
            " explicitly confirmed."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "routine_name": types.Schema(type=types.Type.STRING),
            },
            required=["routine_name"],
        ),
    ),
]


def handle_routine_tool(
    name: str, inputs: dict, db: Session, user_id: int
) -> str:
    """Dispatch a routine tool call; return result as a JSON string."""
    if name == "get_routines":
        routines = (
            db.query(Routine)
            .options(
                joinedload(Routine.exercises).joinedload(
                    RoutineExercise.exercise_def
                )
            )
            .filter(Routine.user_id == user_id)
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
                    for ex in sorted(
                        r.exercises, key=lambda x: x.position
                    )
                ],
            }
            for r in routines
        ]
        return json.dumps({"routines": result, "count": len(result)})

    if name == "create_routine":
        all_ex = _all_exercises_with_muscles(db, user_id)
        ex_by_name = {e.name.lower(): e for e in all_ex}
        exercise_reqs, not_found = _resolve_routine_exercises(
            inputs["exercises"], ex_by_name, all_ex
        )
        if not_found:
            return json.dumps({
                "error": (
                    f"Exercises not found: {', '.join(not_found)}."
                    " Use search_exercises to find the correct name."
                )
            })
        data = RoutineCreate(
            name=inputs["name"], exercises=exercise_reqs
        )
        try:
            routine = _create_routine(db, data, user_id)
        except ValueError as e:
            if str(e) == "name_conflict":
                return json.dumps({
                    "error": (
                        f"You already have a routine named"
                        f" '{inputs['name']}'."
                    )
                })
            raise
        return json.dumps({
            "success": True,
            "routine_id": routine.id,
            "name": routine.name,
            "exercises": len(exercise_reqs),
        })

    if name == "update_routine":
        routine_or_err = _resolve_routine(
            inputs["routine_name"], db, user_id
        )
        if isinstance(routine_or_err, dict):
            return json.dumps(routine_or_err)
        routine = routine_or_err
        new_name = inputs.get("new_name") or routine.name
        if inputs.get("exercises"):
            all_ex = _all_exercises_with_muscles(db, user_id)
            ex_by_name = {e.name.lower(): e for e in all_ex}
            exercise_reqs, not_found = _resolve_routine_exercises(
                inputs["exercises"], ex_by_name, all_ex
            )
            if not_found:
                return json.dumps({
                    "error": (
                        f"Exercises not found: {', '.join(not_found)}."
                    )
                })
        else:
            exercise_reqs = [
                RoutineExerciseRequest(
                    exercise_id=ex.exercise_id,
                    position=ex.position,
                    num_sets=ex.num_sets,
                )
                for ex in sorted(
                    routine.exercises, key=lambda x: x.position
                )
            ]
        data = RoutineUpdate(name=new_name, exercises=exercise_reqs)
        try:
            updated = _update_routine(db, routine.id, data, user_id)
        except ValueError as e:
            if str(e) == "name_conflict":
                return json.dumps({
                    "error": (
                        f"You already have a routine named '{new_name}'."
                    )
                })
            raise
        if not updated:
            return json.dumps({"error": "Routine not found."})
        return json.dumps({
            "success": True,
            "routine_id": updated.id,
            "name": updated.name,
        })

    if name == "delete_routine":
        routine_or_err = _resolve_routine(
            inputs["routine_name"], db, user_id
        )
        if isinstance(routine_or_err, dict):
            return json.dumps(routine_or_err)
        routine = routine_or_err
        found = _delete_routine(db, routine.id, user_id)
        if not found:
            return json.dumps({"error": "Routine not found."})
        return json.dumps({"success": True, "deleted": routine.name})

    return json.dumps({"error": f"Unknown routine tool: {name}"})
