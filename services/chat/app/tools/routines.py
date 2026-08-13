import json

from google.genai import types

from app.client.api_client import api_client
from app.tools.base import _best_exercise_match, _resolve_routine

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


def _resolve_routine_exercises(
    exercise_inputs: list[dict],
    ex_by_name: dict,
    all_ex: list[dict],
) -> tuple[list[dict], list[str]]:
    """Resolve exercise name dicts to routine exercise request dicts.

    Returns (request_dicts, not_found_names). Each dict has keys:
    exercise_id, position, num_sets.
    """
    requests: list[dict] = []
    not_found: list[str] = []
    for i, ex in enumerate(exercise_inputs):
        name_lower = ex["exercise_name"].lower()
        match = ex_by_name.get(name_lower) or _best_exercise_match(
            name_lower.split(), all_ex
        )
        if not match:
            not_found.append(ex["exercise_name"])
            continue
        requests.append({
            "exercise_id": match["id"],
            "position": i + 1,
            "num_sets": ex["sets"],
        })
    return requests, not_found


def handle_routine_tool(
    name: str, inputs: dict, token: str
) -> str:
    """Dispatch a routine tool call; return result as a JSON string."""
    if name == "get_routines":
        try:
            summaries = api_client.get_routines(token)
            routines = [
                api_client.get_routine(token, r["id"]) for r in summaries
            ]
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"routines": routines, "count": len(routines)})

    if name == "create_routine":
        all_ex = api_client.get_exercises(token)
        ex_by_name = {e["name"].lower(): e for e in all_ex}
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
        data = {"name": inputs["name"], "exercises": exercise_reqs}
        try:
            result = api_client.post_routine(token, data)
        except Exception as exc:
            err = str(exc)
            if "409" in err:
                return json.dumps({
                    "error": (
                        f"You already have a routine named '{inputs['name']}'."
                    )
                })
            return json.dumps({"error": err})
        return json.dumps({
            "success": True,
            "routine_id": result["id"],
            "name": result["name"],
            "exercises": len(exercise_reqs),
        })

    if name == "update_routine":
        routines = api_client.get_routines(token)
        routine_or_err = _resolve_routine(inputs["routine_name"], routines)
        if "error" in routine_or_err:
            return json.dumps(routine_or_err)
        routine = routine_or_err
        new_name = inputs.get("new_name") or routine["name"]
        if inputs.get("exercises"):
            all_ex = api_client.get_exercises(token)
            ex_by_name = {e["name"].lower(): e for e in all_ex}
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
            full_routine = api_client.get_routine(token, routine["id"])
            exercise_reqs = [
                {
                    "exercise_id": ex["exercise_id"],
                    "position": ex["position"],
                    "num_sets": ex["num_sets"],
                }
                for ex in sorted(
                    full_routine.get("exercises", []),
                    key=lambda x: x["position"],
                )
            ]
        data = {"name": new_name, "exercises": exercise_reqs}
        try:
            result = api_client.put_routine(token, routine["id"], data)
        except Exception as exc:
            err = str(exc)
            if "409" in err:
                return json.dumps({
                    "error": f"You already have a routine named '{new_name}'."
                })
            return json.dumps({"error": err})
        return json.dumps({
            "success": True,
            "routine_id": result["id"],
            "name": result["name"],
        })

    if name == "delete_routine":
        routines = api_client.get_routines(token)
        routine_or_err = _resolve_routine(inputs["routine_name"], routines)
        if "error" in routine_or_err:
            return json.dumps(routine_or_err)
        routine = routine_or_err
        try:
            api_client.delete_routine(token, routine["id"])
        except Exception as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"success": True, "deleted": routine["name"]})

    return json.dumps({"error": f"Unknown routine tool: {name}"})
