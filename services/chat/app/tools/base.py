import json


def _resolve_exercise_names(
    inputs: list[dict],
    ex_by_name: dict[str, dict],
    all_ex: list[dict],
) -> tuple[list[tuple[dict, dict]], list[str]]:
    """Resolve exercise name dicts to (input, exercise) pairs.

    Returns (matched_pairs, not_found_names). Each pair is
    (input_dict, exercise_dict) for downstream callers to shape.
    """
    pairs: list[tuple[dict, dict]] = []
    not_found: list[str] = []
    for inp in inputs:
        name_lower = inp["exercise_name"].lower()
        match = ex_by_name.get(name_lower) or _best_exercise_match(
            name_lower.split(), all_ex
        )
        if not match:
            not_found.append(inp["exercise_name"])
        else:
            pairs.append((inp, match))
    return pairs, not_found


def _not_found_error(names: list[str]) -> str:
    """Return a JSON error string for unresolved exercise names."""
    return json.dumps({
        "error": (
            f"Exercises not found: {', '.join(names)}."
            " Use search_exercises to find the correct name."
        )
    })


def _best_exercise_match(
    query_words: list[str], exercises: list[dict]
) -> dict | None:
    """Return the best matching exercise dict, or None if no match.

    Prefers full-word match over substring match.
    """
    q_set = set(query_words)
    word_matches = [
        e for e in exercises
        if q_set.issubset(set(e["name"].lower().split()))
    ]
    if word_matches:
        return word_matches[0]
    query_str = " ".join(query_words)
    sub_matches = [e for e in exercises if query_str in e["name"].lower()]
    return sub_matches[0] if sub_matches else None


def _resolve_muscle_groups(
    names: list[str], all_exercises: list[dict]
) -> tuple[list[int], list[str]]:
    """Resolve muscle group name strings to IDs using exercise data.

    Returns (matched_ids, unresolved_names). Extracts unique muscle
    groups from the exercises list (each exercise has muscle_groups list
    with id and name).
    """
    seen: dict[str, int] = {}
    for ex in all_exercises:
        for mg in ex.get("muscle_groups", []):
            seen[mg["name"].lower()] = mg["id"]

    matched_ids: list[int] = []
    unresolved: list[str] = []
    for name in names:
        q = name.lower()
        match_id = next(
            (mid for mname, mid in seen.items() if q in mname), None
        )
        if match_id is not None:
            matched_ids.append(match_id)
        else:
            unresolved.append(name)
    return matched_ids, unresolved


def _resolve_routine(
    name: str, routines: list[dict]
) -> dict:
    """Return matching routine dict or an error dict.

    Returns error dict if zero or multiple routines match.
    """
    q = name.lower()
    matches = [r for r in routines if q in r["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return {
            "error": (
                f"Multiple routines match '{name}': "
                f"{[r['name'] for r in matches]}. Be more specific."
            )
        }
    names = [r["name"] for r in routines]
    return {
        "error": (
            f"No routine found matching '{name}'. "
            f"Your routines: {names}"
        )
    }
