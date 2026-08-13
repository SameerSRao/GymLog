import json
import os
import time
from pathlib import Path
from typing import Generator

from google import genai
from google.genai import types

from app.client.api_client import api_client
from app.tools import TOOLS, execute_tool

_client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))
_MODEL = "gemini-3-flash-preview"

_CONTEXT_DIR = Path(__file__).parent.parent / "context"
_SYSTEM_PROMPT = (_CONTEXT_DIR / "system_prompt.md").read_text()
_KNOWLEDGE = (_CONTEXT_DIR / "knowledge.md").read_text()

_MAX_HISTORY = 20
_MAX_TOOL_ROUNDS = 10


def _build_dynamic_context(token: str) -> str:
    """Return a training-data summary string for the system prompt."""
    workouts = api_client.get_workouts(token)
    total = len(workouts)
    last_logged = (
        workouts[0]["logged_at"][:10] if workouts else "never"
    )
    routines = api_client.get_routines(token)
    routine_names = [r["name"] for r in routines]

    lines = [
        "## Your User's Training Data",
        f"Total workouts logged: {total}",
        f"Last workout: {last_logged}",
    ]
    if routine_names:
        lines.append(f"Saved routines: {', '.join(routine_names)}")
    return "\n".join(lines)


def run_chat(
    token: str,
    messages: list[dict[str, str]],
    local_time: str | None = None,
) -> Generator[str, None, None]:
    """Run the Gemini tool loop for token; yield SSE text chunks."""
    dynamic_context = _build_dynamic_context(token)
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
                    fc.name, dict(fc.args), token, local_time=local_time,
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
        yield (
            "Sorry, I wasn't able to complete that request."
            " Please try again."
        )
