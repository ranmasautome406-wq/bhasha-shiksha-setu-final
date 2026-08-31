#!/usr/bin/env python3
"""
Create the first admin account (or reset its password).
Usage:
    python create_admin.py                    # uses .env ADMIN_EMAIL/ADMIN_PASSWORD
    python create_admin.py user@site.com MyPass#123
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import create_app
from backend.database import db
from backend.models import User
from backend.utils import hash_password
from backend.config import Config

app = create_app()


def main():
    with app.app_context():
        email = sys.argv[1] if len(sys.argv) > 1 else Config.ADMIN_EMAIL
        password = sys.argv[2] if len(sys.argv) > 2 else Config.ADMIN_PASSWORD
        name = os.getenv("ADMIN_NAME", "Administrator")
        email = email.strip().lower()

        if len(password) < 6:
            print("Password must be at least 6 characters.")
            sys.exit(1)

        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.active = True
            db.session.commit()
            print(f"✔ Admin '{email}' updated — password reset, role set to admin.")
        else:
            user = User(name=name, email=email, role="admin",
                        password_hash=hash_password(password))
            db.session.add(user)
            db.session.commit()
            print(f"✔ Admin created: {email}")
        print("You can log in at:  http://localhost:5000/admin")
        print("⚠  Change this password after your first login (Profile → Change Password).")


if __name__ == "__main__":
    main()
