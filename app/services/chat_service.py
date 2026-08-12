import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Generator

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.services.chat_tools import TOOLS, execute_tool
from app.services.routine_service import get_all_routines
from app.services.workout_service import get_all_workouts

_client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))
_MODEL = "gemini-3-flash-preview"

_CONTEXT_DIR = Path(__file__).parent.parent / "context"
_SYSTEM_PROMPT = (_CONTEXT_DIR / "system_prompt.md").read_text()
_KNOWLEDGE = (_CONTEXT_DIR / "knowledge.md").read_text()

_MAX_HISTORY = 20
_MAX_TOOL_ROUNDS = 10


def _build_dynamic_context(db: Session, user_id: int) -> str:
    """Return a short string summarising the user's data for the system prompt."""
    workouts = get_all_workouts(db, user_id)
    total = len(workouts)

    exercise_counts: Counter = Counter()
    for w in workouts:
        for s in w.sets:
            exercise_counts[s.exercise_def.name] += 1

    top = [name for name, _ in exercise_counts.most_common(5)]
    routines = get_all_routines(db, user_id)
    routine_names = [r.name for r in routines]
    last_logged = (
        workouts[0].logged_at.strftime("%Y-%m-%d") if workouts else "never"
    )

    lines = [
        "## Your User's Training Data",
        f"Total workouts logged: {total}",
        f"Last workout: {last_logged}",
    ]
    if top:
        lines.append(f"Most logged exercises: {', '.join(top)}")
    if routine_names:
        lines.append(f"Saved routines: {', '.join(routine_names)}")
    return "\n".join(lines)


def run_chat(
    db: Session,
    messages: list[dict[str, str]],
    user_id: int,
    local_time: str | None = None,
) -> Generator[str, None, None]:
    """Run the agentic tool loop for user_id; yield text chunks for SSE streaming."""
    dynamic_context = _build_dynamic_context(db, user_id)
    parts = [_SYSTEM_PROMPT, _KNOWLEDGE, dynamic_context]
    if local_time:
        parts.append(f"User's current local time: {local_time}")
    system_content = "\n\n".join(parts)

    recent = messages[-_MAX_HISTORY:]
    contents: list[types.Content] = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part.from_text(text=m["content"])],
        )
        for m in recent
    ]

    config = types.GenerateContentConfig(
        system_instruction=system_content,
        tools=[TOOLS],
    )

    for _ in range(_MAX_TOOL_ROUNDS):
        for attempt in range(4):
            try:
                response = _client.models.generate_content(
                    model=_MODEL,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as exc:
                if "429" in str(exc) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise

        candidate = response.candidates[0]
        func_calls = [
            p.function_call
            for p in candidate.content.parts
            if p.function_call is not None
        ]

        if not func_calls:
            yield response.text or ""
            break

        contents.append(candidate.content)

        result_parts = []
        for fc in func_calls:
            result = json.loads(
                execute_tool(
                    fc.name, dict(fc.args), db, user_id,
                    local_time=local_time,
                )
            )
            result_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response=result,
                )
            )

        contents.append(types.Content(role="user", parts=result_parts))
    else:
        yield "Sorry, I wasn't able to complete that request. Please try again."
