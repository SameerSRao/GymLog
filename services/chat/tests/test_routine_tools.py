import json
from unittest.mock import patch

from app.tools.routines import handle_routine_tool

TOKEN = "fake-token"

EXERCISES = [
    {"id": 1, "name": "Bench Press", "muscle_groups": []},
    {"id": 2, "name": "Squat", "muscle_groups": []},
]

ROUTINES = [
    {"id": 10, "name": "Push Day"},
]

ROUTINE_DETAIL = {
    "id": 10,
    "name": "Push Day",
    "exercises": [
        {"exercise_id": 1, "position": 1, "num_sets": 3},
    ],
}


@patch("app.tools.routines.api_client")
def test_get_routines_returns_all(mock_api):
    """Returns all routines with full detail."""
    mock_api.get_routines.return_value = ROUTINES
    mock_api.get_routine.return_value = ROUTINE_DETAIL
    result = json.loads(handle_routine_tool("get_routines", {}, TOKEN))
    assert result["count"] == 1
    assert result["routines"][0]["name"] == "Push Day"


@patch("app.tools.routines.api_client")
def test_create_routine_success(mock_api):
    """Returns success payload when exercises resolve and API call succeeds."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.post_routine.return_value = {"id": 20, "name": "Pull Day"}
    inputs = {
        "name": "Pull Day",
        "exercises": [{"exercise_name": "Squat", "sets": 4}],
    }
    result = json.loads(handle_routine_tool("create_routine", inputs, TOKEN))
    assert result["success"] is True
    assert result["name"] == "Pull Day"


@patch("app.tools.routines.api_client")
def test_create_routine_unknown_exercise(mock_api):
    """Returns error when an exercise name cannot be resolved."""
    mock_api.get_exercises.return_value = EXERCISES
    inputs = {
        "name": "Ghost Routine",
        "exercises": [{"exercise_name": "Unicorn Lift", "sets": 3}],
    }
    result = json.loads(handle_routine_tool("create_routine", inputs, TOKEN))
    assert "error" in result
    assert "Unicorn Lift" in result["error"]


@patch("app.tools.routines.api_client")
def test_create_routine_duplicate_name(mock_api):
    """Returns a friendly error on 409 duplicate name."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.post_routine.side_effect = Exception("409 Conflict")
    inputs = {
        "name": "Push Day",
        "exercises": [{"exercise_name": "Bench Press", "sets": 3}],
    }
    result = json.loads(handle_routine_tool("create_routine", inputs, TOKEN))
    assert "error" in result
    assert "Push Day" in result["error"]


@patch("app.tools.routines.api_client")
def test_update_routine_name_only(mock_api):
    """Updates name and preserves exercises when exercises is omitted."""
    mock_api.get_routines.return_value = ROUTINES
    mock_api.get_routine.return_value = ROUTINE_DETAIL
    mock_api.put_routine.return_value = {"id": 10, "name": "New Name"}
    inputs = {"routine_name": "Push Day", "new_name": "New Name"}
    result = json.loads(handle_routine_tool("update_routine", inputs, TOKEN))
    assert result["success"] is True
    assert result["name"] == "New Name"
    put_data = mock_api.put_routine.call_args[0][2]
    assert len(put_data["exercises"]) == 1


@patch("app.tools.routines.api_client")
def test_update_routine_replaces_exercises(mock_api):
    """Sends a new exercise list when exercises is provided."""
    mock_api.get_routines.return_value = ROUTINES
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.put_routine.return_value = {"id": 10, "name": "Push Day"}
    inputs = {
        "routine_name": "Push Day",
        "exercises": [
            {"exercise_name": "Squat", "sets": 5},
        ],
    }
    result = json.loads(handle_routine_tool("update_routine", inputs, TOKEN))
    assert result["success"] is True
    put_data = mock_api.put_routine.call_args[0][2]
    assert put_data["exercises"][0]["exercise_id"] == 2


@patch("app.tools.routines.api_client")
def test_update_routine_not_found(mock_api):
    """Returns error when no routine matches the given name."""
    mock_api.get_routines.return_value = ROUTINES
    inputs = {"routine_name": "Nonexistent"}
    result = json.loads(handle_routine_tool("update_routine", inputs, TOKEN))
    assert "error" in result


@patch("app.tools.routines.api_client")
def test_delete_routine_success(mock_api):
    """Returns success when routine is found and deleted."""
    mock_api.get_routines.return_value = ROUTINES
    mock_api.delete_routine.return_value = None
    result = json.loads(
        handle_routine_tool(
            "delete_routine", {"routine_name": "Push Day"}, TOKEN
        )
    )
    assert result["success"] is True
    assert result["deleted"] == "Push Day"


@patch("app.tools.routines.api_client")
def test_delete_routine_ambiguous_name(mock_api):
    """Returns error when multiple routines match the given name."""
    mock_api.get_routines.return_value = [
        {"id": 1, "name": "Push Day A"},
        {"id": 2, "name": "Push Day B"},
    ]
    result = json.loads(
        handle_routine_tool(
            "delete_routine", {"routine_name": "Push Day"}, TOKEN
        )
    )
    assert "error" in result
    assert "Multiple" in result["error"]
