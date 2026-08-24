from datetime import datetime

from pydantic import BaseModel


class MuscleGroupSchema(BaseModel):
    """Response schema for a muscle group."""

    id: int
    name: str


class ExerciseDefSchema(BaseModel):
    """Response schema for an exercise definition."""

    id: int
    name: str
    equipment: str | None = None
    instructions: str | None = None
    user_id: int | None = None
    muscle_groups: list[MuscleGroupSchema]


class CreateExerciseSchema(BaseModel):
    """Request schema for creating a new exercise."""

    name: str
    equipment: str | None = None
    instructions: str | None = None
    muscle_group_ids: list[int]


class ExerciseUpdate(BaseModel):
    """Request schema for partially updating an exercise; all optional."""

    name: str | None = None
    equipment: str | None = None
    instructions: str | None = None
    muscle_group_ids: list[int] | None = None


class SetDetail(BaseModel):
    """One set with its set number, used in progression responses."""

    set_number: int
    reps: int
    weight_lbs: float | None = None
    estimated_1rm: float | None = None


class SessionSummary(BaseModel):
    """Aggregated summary of one session for a single exercise's progression."""

    session_id: int
    logged_at: datetime
    sets: list[SetDetail]
    volume: float | None = None
    best_set_weight: float | None = None


class ExerciseProgressionSchema(BaseModel):
    """Response schema for an exercise's progression history."""

    exercise_id: int
    exercise_name: str
    sessions: list[SessionSummary]
