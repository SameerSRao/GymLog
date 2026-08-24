from datetime import datetime

from pydantic import BaseModel, field_validator

from app.exercises.schemas import MuscleGroupSchema


class SetSchema(BaseModel):
    """One set in a workout log request or response."""

    reps: int
    weight_lbs: float | None = None

    @field_validator('reps')
    @classmethod
    def reps_non_negative(cls, v: int) -> int:
        """Reject negative rep counts."""
        if v < 0:
            raise ValueError('reps must be >= 0')
        return v


class ExerciseLogRequest(BaseModel):
    """One exercise entry (with sets) inside a workout log request."""

    exercise_id: int
    sets: list[SetSchema]


class WorkoutRequest(BaseModel):
    """Request schema for creating or replacing a workout session."""

    exercises: list[ExerciseLogRequest]
    notes: str | None = None
    logged_at: datetime | None = None


class ExerciseSchema(BaseModel):
    """One exercise with sets, as returned in a detailed workout response."""

    exercise_id: int
    name: str
    muscle_groups: list[MuscleGroupSchema]
    sets: list[SetSchema]


class WorkoutResponse(BaseModel):
    """Summary response for creating or listing workout sessions."""

    session_id: int
    logged_at: datetime
    exercises_logged: int
    sets_logged: int


class WorkoutDetailed(BaseModel):
    """Full workout detail response including all exercises and sets."""

    session_id: int
    logged_at: datetime
    notes: str | None = None
    exercises: list[ExerciseSchema]


class WorkoutImportRequest(BaseModel):
    """One session in a batch import request; logged_at is required."""

    logged_at: datetime
    exercises: list[ExerciseLogRequest]


class ImportError(BaseModel):
    """One skipped session reported in a batch import response."""

    index: int
    reason: str


class ImportResponse(BaseModel):
    """Summary returned after a batch import completes."""

    sessions_created: int
    sets_created: int
    errors: list[ImportError]
