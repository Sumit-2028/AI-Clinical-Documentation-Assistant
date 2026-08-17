from .database import Base, engine
from .auth.model import User


def init_database():
    Base.metadata.create_all(
        bind=engine
    )


if __name__ == "__main__":
    init_database()