import json
from unittest.mock import patch

from app.tools.exercises import handle_exercise_tool

TOKEN = "fake-token"

EXERCISES = [
    {
        "id": 1,
        "name": "Bench Press",
        "equipment": "barbell",
        "muscle_groups": [{"id": 1, "name": "Chest"}],
    },
    {
        "id": 2,
        "name": "Barbell Row",
        "equipment": "barbell",
        "muscle_groups": [{"id": 2, "name": "Back"}],
    },
]


@patch("app.tools.exercises.api_client")
def test_search_exercises_by_name(mock_api):
    """Returns exercises whose name contains the query."""
    mock_api.get_exercises.return_value = EXERCISES
    result = json.loads(
        handle_exercise_tool("search_exercises", {"query": "bench"}, TOKEN)
    )
    assert result["count"] == 1
    assert result["matches"][0]["name"] == "Bench Press"


@patch("app.tools.exercises.api_client")
def test_search_exercises_by_muscle_group(mock_api):
    """Returns exercises whose muscle group contains the query."""
    mock_api.get_exercises.return_value = EXERCISES
    result = json.loads(
        handle_exercise_tool("search_exercises", {"query": "back"}, TOKEN)
    )
    assert result["count"] == 1
    assert result["matches"][0]["name"] == "Barbell Row"


@patch("app.tools.exercises.api_client")
def test_get_exercise_progression_returns_sessions(mock_api):
    """Returns session history for a matched exercise."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.get_exercise_progression.return_value = {
        "sessions": [
            {"logged_at": "2099-01-01T10:00:00", "sets": [], "volume": 1000,
             "best_set_weight": 135},
        ]
    }
    result = json.loads(
        handle_exercise_tool(
            "get_exercise_progression",
            {"exercise_name": "Bench Press"},
            TOKEN,
        )
    )
    assert result["exercise"] == "Bench Press"
    assert len(result["sessions"]) == 1


@patch("app.tools.exercises.api_client")
def test_get_exercise_progression_no_match(mock_api):
    """Returns error when no exercise name matches the query."""
    mock_api.get_exercises.return_value = EXERCISES
    result = json.loads(
        handle_exercise_tool(
            "get_exercise_progression",
            {"exercise_name": "Ghost Exercise"},
            TOKEN,
        )
    )
    assert "error" in result


@patch("app.tools.exercises.api_client")
def test_get_exercise_progression_no_logged_data(mock_api):
    """Returns error when the matched exercise has no logged sessions."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.get_exercise_progression.return_value = {"sessions": []}
    result = json.loads(
        handle_exercise_tool(
            "get_exercise_progression",
            {"exercise_name": "Bench Press"},
            TOKEN,
        )
    )
    assert "error" in result


@patch("app.tools.exercises.api_client")
def test_create_exercise_success(mock_api):
    """Returns success when muscle groups resolve and API call succeeds."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.post_exercise.return_value = {"id": 99, "name": "Cable Fly"}
    inputs = {
        "name": "Cable Fly",
        "equipment": "cable",
        "muscle_group_names": ["Chest"],
    }
    result = json.loads(
        handle_exercise_tool("create_exercise", inputs, TOKEN)
    )
    assert result["success"] is True
    assert result["name"] == "Cable Fly"


@patch("app.tools.exercises.api_client")
def test_create_exercise_unknown_muscle_group(mock_api):
    """Returns error when a muscle group name cannot be resolved."""
    mock_api.get_exercises.return_value = EXERCISES
    inputs = {
        "name": "Ghost Lift",
        "muscle_group_names": ["Unicorn Muscle"],
    }
    result = json.loads(
        handle_exercise_tool("create_exercise", inputs, TOKEN)
    )
    assert "error" in result
    assert "Unicorn Muscle" in result["error"]


@patch("app.tools.exercises.api_client")
def test_update_exercise_success(mock_api):
    """Returns success when exercise resolves and API call succeeds."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.put_exercise.return_value = {"id": 1, "name": "Bench Press"}
    inputs = {"exercise_name": "Bench Press", "equipment": "dumbbell"}
    result = json.loads(
        handle_exercise_tool("update_exercise", inputs, TOKEN)
    )
    assert result["success"] is True


@patch("app.tools.exercises.api_client")
def test_update_exercise_permission_denied(mock_api):
    """Returns a friendly error message on 403."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.put_exercise.side_effect = Exception("403 Forbidden")
    inputs = {"exercise_name": "Bench Press", "equipment": "dumbbell"}
    result = json.loads(
        handle_exercise_tool("update_exercise", inputs, TOKEN)
    )
    assert "permission" in result["error"].lower()


@patch("app.tools.exercises.api_client")
def test_delete_exercise_success(mock_api):
    """Returns success when exercise is found and deleted."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.delete_exercise.return_value = None
    result = json.loads(
        handle_exercise_tool(
            "delete_exercise", {"exercise_name": "Bench Press"}, TOKEN
        )
    )
    assert result["success"] is True
    assert result["deleted"] == "Bench Press"


@patch("app.tools.exercises.api_client")
def test_delete_exercise_has_history(mock_api):
    """Returns a friendly error when exercise has workout history (409)."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.delete_exercise.side_effect = Exception("409 Conflict")
    result = json.loads(
        handle_exercise_tool(
            "delete_exercise", {"exercise_name": "Bench Press"}, TOKEN
        )
    )
    assert "error" in result
    assert "history" in result["error"].lower()
