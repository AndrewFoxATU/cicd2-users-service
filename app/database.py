# backend/users_service/database.py
import os, time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

POSTGRES_USER = os.getenv("POSTGRES_USER", "users_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "users_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "users_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres_users")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"
RETRIES = int(os.getenv("DB_RETRIES", "15"))
DELAY = float(os.getenv("DB_RETRY_DELAY", "2"))

engine = None
for attempt in range(RETRIES):
    try:
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            echo=SQL_ECHO,
        )
        with engine.connect():
            print("Connected to PostgreSQL")
        break
    except OperationalError:
        print(f"Postgres not ready (attempt {attempt + 1}/{RETRIES})")
        time.sleep(DELAY)

if engine is None:
    raise RuntimeError("Could not connect to PostgreSQL after several attempts.")

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
