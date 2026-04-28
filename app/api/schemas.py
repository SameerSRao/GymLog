from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SetSchema(BaseModel):
    reps: int
    weight_lbs: Optional[float] = None


class ExerciseSchema(BaseModel):
    name: str
    muscle_group: str
    sets: list[SetSchema]


class WorkoutRequest(BaseModel):
    exercises: list[ExerciseSchema]


class WorkoutResponse(BaseModel):
    session_id: int
    logged_at: datetime
    exercises_logged: int
    sets_logged: int


class WorkoutDetailed(BaseModel):
    session_id: int
    logged_at: datetime
    exercises: list[ExerciseSchema]