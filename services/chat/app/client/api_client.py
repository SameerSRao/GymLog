import os

import httpx

_API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


def _auth(token: str) -> dict:
    """Return Authorization header dict for token."""
    return {"Authorization": f"Bearer {token}"}


class ApiClient:
    """Sync httpx client for calling the core API service."""

    def __init__(self, base_url: str = _API_BASE_URL) -> None:
        """Initialise the client with the core API base URL."""
        self._client = httpx.Client(
            base_url=base_url, timeout=30.0
        )

    def get_me(self, token: str) -> dict:
        """Return current user's profile flags from GET /api/auth/me."""
        r = self._client.get("/api/auth/me", headers=_auth(token))
        r.raise_for_status()
        return r.json()

    def get_exercises(self, token: str) -> list[dict]:
        """Return all exercises visible to user from GET /api/exercises."""
        r = self._client.get("/api/exercises", headers=_auth(token))
        r.raise_for_status()
        return r.json()

    def post_exercise(self, token: str, data: dict) -> dict:
        """Create an exercise via POST /api/exercises."""
        r = self._client.post(
            "/api/exercises", json=data, headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def put_exercise(
        self, token: str, exercise_id: int, data: dict
    ) -> dict:
        """Update an exercise via PUT /api/exercise/{id}."""
        r = self._client.put(
            f"/api/exercise/{exercise_id}",
            json=data,
            headers=_auth(token),
        )
        r.raise_for_status()
        return r.json()

    def delete_exercise(self, token: str, exercise_id: int) -> bool:
        """Delete an exercise via DELETE /api/exercise/{id}."""
        r = self._client.delete(
            f"/api/exercise/{exercise_id}", headers=_auth(token)
        )
        return r.status_code == 204

    def get_exercise_progression(
        self, token: str, exercise_id: int
    ) -> dict:
        """Return progression data from GET /api/exercise/{id}/progression."""
        r = self._client.get(
            f"/api/exercise/{exercise_id}/progression",
            headers=_auth(token),
        )
        r.raise_for_status()
        return r.json()

    def get_workouts(
        self,
        token: str,
        year: int | None = None,
        month: int | None = None,
    ) -> list[dict]:
        """Return workout summaries from GET /api/workouts."""
        params = {}
        if year is not None:
            params["year"] = year
        if month is not None:
            params["month"] = month
        r = self._client.get(
            "/api/workouts", params=params, headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def get_workout(self, token: str, session_id: int) -> dict:
        """Return a single workout from GET /api/workout/{id}."""
        r = self._client.get(
            f"/api/workout/{session_id}", headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def post_workout(self, token: str, data: dict) -> dict:
        """Log a workout via POST /api/workouts."""
        r = self._client.post(
            "/api/workouts", json=data, headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def put_workout(
        self, token: str, session_id: int, data: dict
    ) -> dict:
        """Replace a workout via PUT /api/workout/{id}."""
        r = self._client.put(
            f"/api/workout/{session_id}",
            json=data,
            headers=_auth(token),
        )
        r.raise_for_status()
        return r.json()

    def delete_workout(self, token: str, session_id: int) -> bool:
        """Delete a workout via DELETE /api/workout/{id}."""
        r = self._client.delete(
            f"/api/workout/{session_id}", headers=_auth(token)
        )
        return r.status_code == 200

    def get_routines(self, token: str) -> list[dict]:
        """Return all routines from GET /api/routines."""
        r = self._client.get("/api/routines", headers=_auth(token))
        r.raise_for_status()
        return r.json()

    def get_routine(self, token: str, routine_id: int) -> dict:
        """Return full routine detail from GET /api/routine/{id}.

        Returns RoutineDetail which includes the exercises list, unlike
        the list endpoint which returns RoutineListItem without exercises.
        Use this method when you need to read or modify a routine's
        exercise list (e.g. in update_routine).
        """
        r = self._client.get(
            f"/api/routine/{routine_id}", headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def post_routine(self, token: str, data: dict) -> dict:
        """Create a routine via POST /api/routines."""
        r = self._client.post(
            "/api/routines", json=data, headers=_auth(token)
        )
        r.raise_for_status()
        return r.json()

    def put_routine(
        self, token: str, routine_id: int, data: dict
    ) -> dict:
        """Replace a routine via PUT /api/routine/{id}."""
        r = self._client.put(
            f"/api/routine/{routine_id}",
            json=data,
            headers=_auth(token),
        )
        r.raise_for_status()
        return r.json()

    def delete_routine(self, token: str, routine_id: int) -> bool:
        """Delete a routine via DELETE /api/routine/{id}."""
        r = self._client.delete(
            f"/api/routine/{routine_id}", headers=_auth(token)
        )
        return r.status_code == 200

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()


api_client = ApiClient()
