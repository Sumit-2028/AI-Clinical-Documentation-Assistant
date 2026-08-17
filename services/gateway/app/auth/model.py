from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import UUID
import uuid

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name = Column(
        String(255),
        nullable=False,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    role = Column(
        String(50),
        nullable=False,
        default="physician",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )