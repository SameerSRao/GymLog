from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Table,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

exercise_muscle_groups = Table(
    "exercise_muscle_groups",
    Base.metadata,
    Column("exercise_id", Integer, ForeignKey("exercises.id"), primary_key=True),
    Column("muscle_group_id", Integer, ForeignKey("muscle_groups.id"), primary_key=True),
)


class MuscleGroup(Base):
    """A named muscle group that can be linked to many exercises."""

    __tablename__ = "muscle_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    exercises: Mapped[list["ExerciseDef"]] = relationship(
        secondary=exercise_muscle_groups, back_populates="muscle_groups"
    )


class User(Base):
    """A registered user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_premium: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_demo: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class ExerciseDef(Base):
    """Definition of an exercise (name, equipment, instructions, muscle groups)."""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    equipment: Mapped[str | None] = mapped_column(String, nullable=True)
    instructions: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    muscle_groups: Mapped[list["MuscleGroup"]] = relationship(
        secondary=exercise_muscle_groups, back_populates="exercises"
    )


class Workout(Base):
    """A workout session — timestamp container; all set data lives in Exercise rows."""

    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_input: Mapped[str | None] = mapped_column(String, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    sets: Mapped[list["Exercise"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Exercise(Base):
    """One set of an exercise logged within a workout session."""

    __tablename__ = "exercise_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workout_sessions.id"), nullable=False
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exercises.id"), nullable=False
    )
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_lbs: Mapped[float | None] = mapped_column(Float, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    session: Mapped["Workout"] = relationship(back_populates="sets")
    exercise_def: Mapped["ExerciseDef"] = relationship()


class Routine(Base):
    """A named workout routine — ordered template of exercises."""

    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    exercises: Mapped[list["RoutineExercise"]] = relationship(
        back_populates="routine",
        cascade="all, delete-orphan",
    )


class RoutineExercise(Base):
    """One exercise slot in a routine with position and default set count."""

    __tablename__ = "routine_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    routine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routines.id"), nullable=False
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exercises.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    num_sets: Mapped[int] = mapped_column(Integer, nullable=False)

    routine: Mapped["Routine"] = relationship(back_populates="exercises")
    exercise_def: Mapped["ExerciseDef"] = relationship()
