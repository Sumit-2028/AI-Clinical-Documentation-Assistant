from .database import check_database_connection


def init_database() -> None:
    check_database_connection()
    print("Database connection OK. Run Alembic migrations to manage schema.")


if __name__ == "__main__":
    init_database()
