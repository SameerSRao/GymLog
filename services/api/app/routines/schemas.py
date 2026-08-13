from datetime import datetime

from pydantic import BaseModel


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
