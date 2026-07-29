import pytest
from app.db.seed import seed_exercises
from app.model.models import ExerciseDef, MuscleGroup


@pytest.mark.slow
def test_seed_populates_exercises(db):
    seed_exercises(db)
    assert db.query(ExerciseDef).count() > 1000
    assert db.query(MuscleGroup).count() > 30


@pytest.mark.slow
def test_seed_is_idempotent(db):
    seed_exercises(db)
    count_after_first = db.query(ExerciseDef).count()
    seed_exercises(db)
    count_after_second = db.query(ExerciseDef).count()
    assert count_after_first == count_after_second


@pytest.mark.slow
def test_seed_aliases_collapsed(db):
    seed_exercises(db)
    assert db.query(MuscleGroup).filter(MuscleGroup.name == "abs").count() == 1
    assert db.query(MuscleGroup).filter(MuscleGroup.name == "abdominals").count() == 0


@pytest.mark.slow
def test_seed_exercises_have_muscle_groups(db):
    seed_exercises(db)
    ex = db.query(ExerciseDef).filter(ExerciseDef.name.ilike("%bench press%")).first()
    assert ex is not None
    assert len(ex.muscle_groups) > 0
