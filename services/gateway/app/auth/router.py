from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db

from .schemas import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)

from .dependencies import get_current_user
from .service import (
    DuplicateEmailError,
    login_user,
    refresh_user_tokens,
    register_user,
    user_response_data,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    tokens = login_user(
        db=db,
        email=request.email,
        password=request.password,
    )

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return tokens


@router.post(
    "/register",
    response_model=UserResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        user = register_user(
            db,
            email=request.email,
            full_name=request.full_name,
            password=request.password,
            role=request.role,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc
    return user_response_data(db, user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
def refresh(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    tokens = refresh_user_tokens(
        db=db,
        refresh_token=request.refresh_token,
    )

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return tokens


@router.get(
    "/me",
    response_model=UserResponse,
    response_model_exclude_none=True,
)
def me(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_response_data(db, current_user)
