import json

from google.genai import types

from app.tools.exercises import EXERCISE_DECLARATIONS, handle_exercise_tool
from app.tools.routines import ROUTINE_DECLARATIONS, handle_routine_tool
from app.tools.workouts import WORKOUT_DECLARATIONS, handle_workout_tool

TOOLS = types.Tool(
    function_declarations=(
        WORKOUT_DECLARATIONS + EXERCISE_DECLARATIONS + ROUTINE_DECLARATIONS
    )
)

_WORKOUT_NAMES = {d.name for d in WORKOUT_DECLARATIONS}
_EXERCISE_NAMES = {d.name for d in EXERCISE_DECLARATIONS}
_ROUTINE_NAMES = {d.name for d in ROUTINE_DECLARATIONS}


def execute_tool(
    name: str,
    inputs: dict,
    token: str,
    local_time: str | None = None,
) -> str:
    """Dispatch a tool call by name with user token; return result as JSON."""
    if name in _WORKOUT_NAMES:
        return handle_workout_tool(name, inputs, token, local_time=local_time)
    if name in _EXERCISE_NAMES:
        return handle_exercise_tool(name, inputs, token)
    if name in _ROUTINE_NAMES:
        return handle_routine_tool(name, inputs, token)
    return json.dumps({"error": f"Unknown tool: {name}"})
