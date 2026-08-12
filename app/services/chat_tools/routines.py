import json

from google.genai import types
from sqlalchemy.orm import Session, joinedload

from app.model.models import Routine, RoutineExercise

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

    return json.dumps({"error": f"Unknown routine tool: {name}"})
