"""Database connection (SQLAlchemy).

For development we use SQLite. To move to PostgreSQL / MySQL in production,
simply change DATABASE_URL in .env — nothing else in the code changes.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """Create all tables + migrate + seed (called once at startup)."""
    from backend import models  # ensure models are registered
    db.init_app(app)
    with app.app_context():
        db.create_all()
        from backend.seed import migrate_columns, seed_defaults
        migrate_columns()
        seed_defaults()
