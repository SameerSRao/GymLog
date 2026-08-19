import json

from app.tools.base import _not_found_error, _resolve_exercise_names

EXERCISES = [
    {
        "id": 1,
        "name": "Bench Press",
        "muscle_groups": [{"id": 1, "name": "Chest"}],
    },
    {
        "id": 2,
        "name": "Barbell Row",
        "muscle_groups": [{"id": 2, "name": "Back"}],
    },
    {
        "id": 3,
        "name": "Overhead Press",
        "muscle_groups": [{"id": 3, "name": "Shoulders"}],
    },
]

EX_BY_NAME = {e["name"].lower(): e for e in EXERCISES}


def test_resolve_exercise_names_exact_match():
    """Resolves exercise by exact (case-insensitive) name."""
    inputs = [{"exercise_name": "Bench Press", "sets": []}]
    pairs, not_found = _resolve_exercise_names(inputs, EX_BY_NAME, EXERCISES)
    assert not_found == []
    assert len(pairs) == 1
    assert pairs[0][1]["id"] == 1


def test_resolve_exercise_names_fuzzy_fallback():
    """Falls back to _best_exercise_match when exact name not in dict."""
    inputs = [{"exercise_name": "barbell row", "sets": []}]
    pairs, not_found = _resolve_exercise_names(inputs, EX_BY_NAME, EXERCISES)
    assert not_found == []
    assert pairs[0][1]["id"] == 2


def test_resolve_exercise_names_not_found():
    """Collects unresolvable names in not_found."""
    inputs = [{"exercise_name": "Unicorn Curl", "sets": []}]
    pairs, not_found = _resolve_exercise_names(inputs, EX_BY_NAME, EXERCISES)
    assert pairs == []
    assert not_found == ["Unicorn Curl"]


def test_resolve_exercise_names_mixed():
    """Returns pairs for matches and not_found for misses in one call."""
    inputs = [
        {"exercise_name": "Bench Press", "sets": []},
        {"exercise_name": "Ghost Exercise", "sets": []},
    ]
    pairs, not_found = _resolve_exercise_names(inputs, EX_BY_NAME, EXERCISES)
    assert len(pairs) == 1
    assert pairs[0][1]["id"] == 1
    assert not_found == ["Ghost Exercise"]


def test_not_found_error_single():
    """Returns a JSON error string for a single missing exercise."""
    result = json.loads(_not_found_error(["Curl"]))
    assert "Curl" in result["error"]
    assert "search_exercises" in result["error"]


def test_not_found_error_multiple():
    """Lists all missing exercise names in the error string."""
    result = json.loads(_not_found_error(["Curl", "Squat"]))
    assert "Curl" in result["error"]
    assert "Squat" in result["error"]
