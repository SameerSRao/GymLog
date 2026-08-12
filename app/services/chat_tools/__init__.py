import json

from google.genai import types
from sqlalchemy.orm import Session

from app.services.chat_tools.exercises import (
    EXERCISE_DECLARATIONS,
    handle_exercise_tool,
)
from app.services.chat_tools.routines import (
    ROUTINE_DECLARATIONS,
    handle_routine_tool,
)
from app.services.chat_tools.workouts import (
    WORKOUT_DECLARATIONS,
    handle_workout_tool,
)

TOOLS = types.Tool(
    function_declarations=(
        WORKOUT_DECLARATIONS + EXERCISE_DECLARATIONS + ROUTINE_DECLARATIONS
    )
)

_WORKOUT_NAMES = {d.name for d in WORKOUT_DECLARATIONS}
_EXERCISE_NAMES = {d.name for d in EXERCISE_DECLARATIONS}
_ROUTINE_NAMES = {d.name for d in ROUTINE_DECLARATIONS}


def execute_tool(
    name: str, inputs: dict, db: Session, user_id: int
) -> str:
    """Dispatch a tool call by name for user_id; return result as JSON."""
    if name in _WORKOUT_NAMES:
        return handle_workout_tool(name, inputs, db, user_id)
    if name in _EXERCISE_NAMES:
        return handle_exercise_tool(name, inputs, db, user_id)
    if name in _ROUTINE_NAMES:
        return handle_routine_tool(name, inputs, db, user_id)
    return json.dumps({"error": f"Unknown tool: {name}"})
