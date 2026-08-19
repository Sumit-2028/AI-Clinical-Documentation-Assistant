from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)
    # Public registration is limited to the existing physician-first flow or
    # an explicitly requested patient account. Admin/staff roles are never
    # self-assignable through this endpoint.
    role: Literal["physician", "patient"] = "physician"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    # Public patient identifiers are numeric strings so they remain stable in
    # JSON and can be entered by clinicians without exposing internal UUIDs.
    patient_id: str | None = None

    model_config = ConfigDict(from_attributes=True)
