from backend.database import Base, engine
from backend import models as _models  # noqa: F401


def migrate() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    migrate()
    print("Database tables ensured.")

