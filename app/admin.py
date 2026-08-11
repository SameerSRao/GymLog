import argparse
import sys

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.model.models import User


def _get_db() -> Session:
    """Return a new database session."""
    return SessionLocal()


def promote(username: str, make_admin: bool, make_premium: bool) -> None:
    """Set is_admin or is_premium on the named user account."""
    db = _get_db()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"User '{username}' not found.")
            sys.exit(1)
        if make_admin:
            user.is_admin = True
        if make_premium:
            user.is_premium = True
        db.commit()
        flags = []
        if make_admin:
            flags.append("admin")
        if make_premium:
            flags.append("premium")
        print(
            f"Promoted '{username}': {', '.join(flags) or 'no changes'}."
        )
    finally:
        db.close()


def main() -> None:
    """Run the GymLog admin CLI."""
    parser = argparse.ArgumentParser(description="GymLog admin CLI")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("promote", help="Grant admin or premium to a user")
    p.add_argument("username", help="Username to promote")
    p.add_argument("--admin", action="store_true", help="Grant admin role")
    p.add_argument(
        "--premium", action="store_true", help="Grant premium role"
    )
    args = parser.parse_args()
    if args.command == "promote":
        promote(args.username, args.admin, args.premium)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
