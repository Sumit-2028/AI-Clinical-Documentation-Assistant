from sqlalchemy.orm import Session

from ..database import SessionLocal

from .model import User
from .security import hash_password


def create_test_user():
    db: Session = SessionLocal()

    try:
        existing = (
            db.query(User)
            .filter(
                User.email == "doctor@example.com"
            )
            .first()
        )

        if existing:
            print("Test physician already exists.")
            return

        user = User(
            email="doctor@example.com",
            full_name="Demo Physician",
            password_hash=hash_password(
                "password123"
            ),
            role="physician",
            is_active=True,
        )

        db.add(user)
        db.commit()

        print("Test physician created.")

    finally:
        db.close()


if __name__ == "__main__":
    create_test_user()