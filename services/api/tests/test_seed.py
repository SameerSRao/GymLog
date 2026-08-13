import pytest

from app.db.seed import seed_exercises
from app.db.models import ExerciseDef, MuscleGroup


@pytest.mark.slow
def test_seed_populates_exercises(db):
    """Assert seed_exercises loads over 1,000 exercises and over 30 muscle groups."""
    seed_exercises(db)
    assert db.query(ExerciseDef).count() > 1000
    assert db.query(MuscleGroup).count() > 30


@pytest.mark.slow
def test_seed_is_idempotent(db):
    """Assert calling seed_exercises twice does not create duplicate exercises."""
    seed_exercises(db)
    count_after_first = db.query(ExerciseDef).count()
    seed_exercises(db)
    count_after_second = db.query(ExerciseDef).count()
    assert count_after_first == count_after_second


@pytest.mark.slow
def test_seed_aliases_collapsed(db):
    """Assert muscle group aliases are collapsed so 'abdominals' is stored as 'abs'."""
    seed_exercises(db)
    assert db.query(MuscleGroup).filter(MuscleGroup.name == "abs").count() == 1
    assert db.query(MuscleGroup).filter(MuscleGroup.name == "abdominals").count() == 0


@pytest.mark.slow
def test_seed_exercises_have_muscle_groups(db):
    """Assert seeded bench press exercises have at least one linked muscle group."""
    seed_exercises(db)
    ex = db.query(ExerciseDef).filter(ExerciseDef.name.ilike("%bench press%")).first()
    assert ex is not None
    assert len(ex.muscle_groups) > 0
