from app.model.models import User


def test_is_admin_flag_persists(db):
    """Assert setting is_admin=True on a User persists after commit."""
    from conftest import make_user
    user = make_user(db, username="alice", is_admin=False)
    user.is_admin = True
    db.commit()
    db.refresh(user)
    assert user.is_admin is True


def test_is_premium_flag_persists(db):
    """Assert setting is_premium=True on a User persists after commit."""
    from conftest import make_user
    user = make_user(db, username="bob", is_premium=False)
    user.is_premium = True
    db.commit()
    db.refresh(user)
    assert user.is_premium is True
