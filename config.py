import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _normalize_db_url(url: str) -> str:
    # Render (and Heroku-style providers) hand out "postgres://", but
    # SQLAlchemy 1.4+/2.x requires the "postgresql://" scheme.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-only-dev-key-not-for-production")

    _database_url = os.environ.get("DATABASE_URL")
    if _database_url:
        # Postgres (Render) — used when DATABASE_URL is set, e.g. in .env
        # locally or in Render's Environment settings when deployed.
        SQLALCHEMY_DATABASE_URI = _normalize_db_url(_database_url)
    else:
        # Fallback: local SQLite file, unchanged from the original setup.
        INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(INSTANCE_DIR, "fitness.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
