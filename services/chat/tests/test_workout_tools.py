import json
from unittest.mock import MagicMock, patch

from app.tools.workouts import handle_workout_tool

TOKEN = "fake-token"

EXERCISES = [
    {"id": 1, "name": "Bench Press", "muscle_groups": []},
    {"id": 2, "name": "Squat", "muscle_groups": []},
]

WORKOUTS = [
    {"session_id": 10, "logged_at": "2099-01-01T10:00:00", "sets_logged": 3},
]

WORKOUT_DETAIL = {
    "exercises": [{"name": "Bench Press"}, {"name": "Bench Press"}],
}


def _client(
    workouts=None,
    workout_detail=None,
    exercises=None,
    post_result=None,
    delete_result=True,
    put_result=None,
):
    """Return a mock api_client with sensible defaults."""
    m = MagicMock()
    m.get_workouts.return_value = workouts or []
    m.get_workout.return_value = workout_detail or {}
    m.get_exercises.return_value = exercises or EXERCISES
    m.post_workout.return_value = post_result or {
        "session_id": 42,
        "logged_at": "2099-01-01T10:00:00",
        "exercises_logged": 1,
    }
    m.delete_workout.return_value = delete_result
    m.put_workout.return_value = put_result or {
        "session_id": 10,
        "exercises_logged": 1,
    }
    return m


@patch("app.tools.workouts.api_client")
def test_get_recent_workouts_within_days(mock_api):
    """Returns workouts logged within the requested day window."""
    mock_api.get_workouts.return_value = WORKOUTS
    mock_api.get_workout.return_value = WORKOUT_DETAIL
    result = json.loads(
        handle_workout_tool("get_recent_workouts", {"days": 3650}, TOKEN)
    )
    assert result["count"] == 1
    assert result["workouts"][0]["session_id"] == 10


@patch("app.tools.workouts.api_client")
def test_get_recent_workouts_excludes_old(mock_api):
    """Excludes workouts outside the day window."""
    old = [{"session_id": 5, "logged_at": "2000-01-01T00:00:00",
             "sets_logged": 1}]
    mock_api.get_workouts.return_value = old
    mock_api.get_workout.return_value = {}
    result = json.loads(
        handle_workout_tool("get_recent_workouts", {"days": 7}, TOKEN)
    )
    assert result["count"] == 0


@patch("app.tools.workouts.api_client")
def test_log_workout_success(mock_api):
    """Returns success payload when exercise resolves and API call succeeds."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.post_workout.return_value = {
        "session_id": 42,
        "logged_at": "2099-01-01T10:00:00",
        "exercises_logged": 1,
    }
    inputs = {
        "exercises": [
            {"exercise_name": "Bench Press", "sets": [{"reps": 8}]},
        ]
    }
    result = json.loads(handle_workout_tool("log_workout", inputs, TOKEN))
    assert result["success"] is True
    assert result["session_id"] == 42


@patch("app.tools.workouts.api_client")
def test_log_workout_unknown_exercise(mock_api):
    """Returns error when an exercise name cannot be resolved."""
    mock_api.get_exercises.return_value = EXERCISES
    inputs = {
        "exercises": [
            {"exercise_name": "Unicorn Curl", "sets": [{"reps": 5}]},
        ]
    }
    result = json.loads(handle_workout_tool("log_workout", inputs, TOKEN))
    assert "error" in result
    assert "Unicorn Curl" in result["error"]


@patch("app.tools.workouts.api_client")
def test_log_workout_uses_local_time_fallback(mock_api):
    """Falls back to local_time when logged_at is not provided."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.post_workout.return_value = {
        "session_id": 1,
        "logged_at": "2099-06-01T09:00:00",
        "exercises_logged": 1,
    }
    inputs = {
        "exercises": [
            {"exercise_name": "Squat", "sets": [{"reps": 5}]},
        ]
    }
    handle_workout_tool("log_workout", inputs, TOKEN, "2099-06-01T09:00:00")
    call_data = mock_api.post_workout.call_args[0][1]
    assert call_data["logged_at"] == "2099-06-01T09:00:00"


@patch("app.tools.workouts.api_client")
def test_delete_workout_success(mock_api):
    """Returns success when the session is found and deleted."""
    mock_api.delete_workout.return_value = True
    result = json.loads(
        handle_workout_tool("delete_workout", {"session_id": 10}, TOKEN)
    )
    assert result["success"] is True
    assert result["deleted_session_id"] == 10


@patch("app.tools.workouts.api_client")
def test_delete_workout_not_found(mock_api):
    """Returns error when delete_workout indicates session not found."""
    mock_api.delete_workout.return_value = False
    result = json.loads(
        handle_workout_tool("delete_workout", {"session_id": 99}, TOKEN)
    )
    assert "error" in result
    assert "99" in result["error"]


@patch("app.tools.workouts.api_client")
def test_update_workout_success(mock_api):
    """Returns success payload when update resolves exercises and succeeds."""
    mock_api.get_exercises.return_value = EXERCISES
    mock_api.put_workout.return_value = {
        "session_id": 10,
        "exercises_logged": 1,
    }
    inputs = {
        "session_id": 10,
        "exercises": [
            {"exercise_name": "Squat", "sets": [{"reps": 5, "weight_lbs": 135}]},
        ],
    }
    result = json.loads(handle_workout_tool("update_workout", inputs, TOKEN))
    assert result["success"] is True
    assert result["session_id"] == 10


@patch("app.tools.workouts.api_client")
def test_update_workout_unknown_exercise(mock_api):
    """Returns error when an exercise name cannot be resolved on update."""
    mock_api.get_exercises.return_value = EXERCISES
    inputs = {
        "session_id": 10,
        "exercises": [
            {"exercise_name": "Ghost Move", "sets": [{"reps": 3}]},
        ],
    }
    result = json.loads(handle_workout_tool("update_workout", inputs, TOKEN))
    assert "error" in result
    assert "Ghost Move" in result["error"]
