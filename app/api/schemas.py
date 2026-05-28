from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MuscleGroupSchema(BaseModel):
    id: int
    name: str


class ExerciseDefSchema(BaseModel):
    id: int
    name: str
    equipment: Optional[str] = None
    target: Optional[str] = None
    instructions: Optional[str] = None
    muscle_groups: list[MuscleGroupSchema]


class CreateExerciseSchema(BaseModel):
    name: str
    muscle_group_ids: list[int]


class SetSchema(BaseModel):
    reps: int
    weight_lbs: Optional[float] = None


# Used in POST /api/workouts request body
class ExerciseLogRequest(BaseModel):
    exercise_id: int
    sets: list[SetSchema]


class WorkoutRequest(BaseModel):
    exercises: list[ExerciseLogRequest]


# Used in workout detail responses
class ExerciseSchema(BaseModel):
    exercise_id: int
    name: str
    muscle_groups: list[MuscleGroupSchema]
    sets: list[SetSchema]


class WorkoutResponse(BaseModel):
    session_id: int
    logged_at: datetime
    exercises_logged: int
    sets_logged: int


class WorkoutDetailed(BaseModel):
    session_id: int
    logged_at: datetime
    exercises: list[ExerciseSchema]


class SetDetail(BaseModel):
    set_number: int
    reps: int
    weight_lbs: Optional[float] = None


class SessionSummary(BaseModel):
    session_id: int
    logged_at: datetime
    sets: list[SetDetail]
    volume: Optional[float] = None
    best_set_weight: Optional[float] = None


class ExerciseProgressionSchema(BaseModel):
    exercise_id: int
    exercise_name: str
    sessions: list[SessionSummary]
