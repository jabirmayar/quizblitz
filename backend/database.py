import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
except Exception:
    # dotenv is optional; environment variables can still be provided by the process manager
    pass

# MySQL connection string format:
# mysql+pymysql://<username>:<password>@<host>:<port>/<db_name>

DEFAULT_DATABASE_URL = "mysql+pymysql://root:@localhost:3306/quiz_system"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# Connect to MySQL (We removed check_same_thread and the SQLite WAL PRAGMAs)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
