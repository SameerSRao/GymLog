import re
from datetime import datetime

from pydantic import BaseModel, field_validator

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{3,30}$")
_PASSWORD_RE = re.compile(r"^[\x20-\x7E]{3,72}$")


class LoginRequest(BaseModel):
    """Request schema for the login endpoint."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Request schema for the register endpoint."""

    username: str
    password: str
    signup_code: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Reject usernames that don't match [a-zA-Z0-9_-]{3,30}."""
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3–30 characters and contain only "
                "letters, numbers, underscores, and hyphens."
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Reject passwords outside printable ASCII or outside 8–72 chars."""
        if not _PASSWORD_RE.match(v):
            raise ValueError(
                "Password must be 3–72 printable characters."
            )
        return v


class TokenResponse(BaseModel):
    """Response schema returned after a successful login."""

    access_token: str
    token_type: str


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
    """Request schema for partially updating an exercise; all fields optional."""

    name: str | None = None
    equipment: str | None = None
    instructions: str | None = None
    muscle_group_ids: list[int] | None = None


class SetSchema(BaseModel):
    """One set in a workout log request or response."""

    reps: int
    weight_lbs: float | None = None


# Used in POST /api/workouts request body
class ExerciseLogRequest(BaseModel):
    """One exercise entry (with sets) inside a workout log request."""

    exercise_id: int
    sets: list[SetSchema]


class WorkoutRequest(BaseModel):
    """Request schema for creating or replacing a workout session."""

    exercises: list[ExerciseLogRequest]
    notes: str | None = None
    logged_at: datetime | None = None


# Used in workout detail responses
class ExerciseSchema(BaseModel):
    """One exercise with its sets, as returned inside a detailed workout response."""

    exercise_id: int
    name: str
    muscle_groups: list[MuscleGroupSchema]
    sets: list[SetSchema]


class WorkoutResponse(BaseModel):
    """Summary response returned after creating or listing workout sessions."""

    session_id: int
    logged_at: datetime
    exercises_logged: int
    sets_logged: int


class WorkoutDetailed(BaseModel):
    """Full workout detail response including all exercises and their sets."""

    session_id: int
    logged_at: datetime
    notes: str | None = None
    exercises: list[ExerciseSchema]


class SetDetail(BaseModel):
    """One set with its set number, used in progression responses."""

    set_number: int
    reps: int
    weight_lbs: float | None = None


class SessionSummary(BaseModel):
    """Aggregated summary of one workout session for a single exercise's progression."""

    session_id: int
    logged_at: datetime
    sets: list[SetDetail]
    volume: float | None = None
    best_set_weight: float | None = None


class ExerciseProgressionSchema(BaseModel):
    """Response schema for an exercise's progression history across sessions."""

    exercise_id: int
    exercise_name: str
    sessions: list[SessionSummary]


class RoutineExerciseRequest(BaseModel):
    """One exercise entry in a routine create/update request."""

    exercise_id: int
    position: int
    num_sets: int


class RoutineCreate(BaseModel):
    """Request schema for creating a new routine."""

    name: str
    exercises: list[RoutineExerciseRequest]


class RoutineUpdate(BaseModel):
    """Request schema for fully replacing a routine's name and exercises."""

    name: str
    exercises: list[RoutineExerciseRequest]


class RoutineExerciseDetail(BaseModel):
    """One exercise slot in a routine detail response."""

    exercise_id: int
    name: str
    position: int
    num_sets: int


class RoutineListItem(BaseModel):
    """Summary of a routine returned in list responses."""

    id: int
    name: str
    exercise_count: int
    created_at: datetime


class RoutineDetail(BaseModel):
    """Full routine response with ordered exercises."""

    id: int
    name: str
    created_at: datetime
    exercises: list[RoutineExerciseDetail]


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
