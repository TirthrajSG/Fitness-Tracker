import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _normalize_db_url(url: str) -> str:
    # Render (and Heroku-style providers) hand out "postgres://", but
    # SQLAlchemy 1.4+/2.x requires the "postgresql://" scheme.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


_database_url = os.environ.get("DATABASE_URL")
if not _database_url:
    sys.exit(
        "DATABASE_URL is not set. This app requires a Postgres connection string.\n"
        "Set it in a .env file for local runs (see .env.example), or in your "
        "Render service's Environment settings when deployed."
    )


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-only-dev-key-not-for-production")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(_database_url)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
