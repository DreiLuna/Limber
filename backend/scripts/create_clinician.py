"""Create a clinician account, or promote an existing user to clinician.

Roles can't be set through the public API, so this script is the only way to make a PT account.

    python -m scripts.create_clinician --email pt@example.com            # prompts for a password
    python -m scripts.create_clinician --email existing@example.com --promote
    python -m scripts.create_clinician --email pt@example.com --demote   # back to patient
"""
import argparse
import getpass
import sys

from sqlalchemy import select

import app.models  # noqa: F401  (registers every table)
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.users.models import User


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", default="", help="display name for a new account")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--promote", action="store_true", help="make an existing user a clinician")
    mode.add_argument("--demote", action="store_true", help="make an existing clinician a patient")
    args = ap.parse_args(argv)
    email = args.email.strip().lower()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if args.promote or args.demote:
            if user is None:
                print(f"No user with email {email}", file=sys.stderr)
                return 1
            user.role = "patient" if args.demote else "clinician"
            db.commit()
            print(f"{email} is now a {user.role}")
            return 0
        if user is not None:
            print(f"{email} already exists; use --promote to make it a clinician", file=sys.stderr)
            return 1
        password = getpass.getpass("Password (min 8 chars): ")
        if len(password) < 8:
            print("Password must be at least 8 characters", file=sys.stderr)
            return 1
        db.add(User(email=email, password_hash=hash_password(password), display_name=args.name, role="clinician"))
        db.commit()
        print(f"Created clinician {email}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
