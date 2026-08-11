def test_user_model_has_expected_columns():
    """Assert User has all required columns."""
    from app.model.models import User
    cols = {c.name for c in User.__table__.columns}
    assert {
        "id", "username", "password_hash",
        "is_admin", "is_premium", "created_at",
    }.issubset(cols)


def test_workout_has_user_id_column():
    """Assert Workout has a non-nullable user_id FK column."""
    from app.model.models import Workout
    col = next(c for c in Workout.__table__.columns if c.name == "user_id")
    assert not col.nullable


def test_routine_has_user_id_column():
    """Assert Routine has a non-nullable user_id FK column."""
    from app.model.models import Routine
    col = next(c for c in Routine.__table__.columns if c.name == "user_id")
    assert not col.nullable


def test_exercise_def_has_nullable_user_id():
    """Assert ExerciseDef has a nullable user_id column."""
    from app.model.models import ExerciseDef
    col = next(
        c for c in ExerciseDef.__table__.columns if c.name == "user_id"
    )
    assert col.nullable is True
