import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
bearer_scheme = HTTPBearer(auto_error=False)

USER_STORE_PATH = Path(__file__).with_name("static.json")
PASSWORD_HASH_ITERATIONS = 600_000
PASSWORD_HASH_ALGORITHM = "sha256"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "shipping-box-calculator"
JWT_LIFETIME = timedelta(minutes=30)
DUMMY_SALT = bytes.fromhex("b2c4a0f1d8e673955aa0bf61c8132490")


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "test@example.com",
                "password": "1234567890",
            }
        }
    )

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class TokenResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "<jwt>",
                "token_type": "bearer",
            }
        }
    )

    access_token: str
    token_type: str = "bearer"


class StoredUser(BaseModel):
    email: str
    password_salt: str
    password_hash: str


def _load_users() -> list[StoredUser]:
    data = json.loads(USER_STORE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("users"), list):
        raise ValueError("The user store must contain a users array.")
    return [StoredUser.model_validate(user) for user in data["users"]]


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        PASSWORD_HASH_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )


def _configured_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="JWT signing is not securely configured.",
        )
    return secret


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Invalid or missing credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Sign in and get a JWT",
    description=(
        "Exchange the demo account email and password for a JWT. "
        "Use the returned access_token as a Bearer token on protected endpoints."
    ),
    responses={
        401: {"description": "Email or password is incorrect."},
        422: {"description": "Login request is invalid."},
        503: {"description": "JWT signing is not securely configured."},
    },
)
def issue_token(credentials: LoginRequest) -> TokenResponse:
    user = next(
        (
            candidate
            for candidate in _load_users()
            if candidate.email == credentials.email
        ),
        None,
    )
    salt = bytes.fromhex(user.password_salt) if user else DUMMY_SALT
    expected_hash = user.password_hash if user else "0" * 64
    actual_hash = _password_digest(credentials.password, salt).hex()
    password_matches = hmac.compare_digest(actual_hash, expected_hash)

    if user is None or not password_matches:
        raise _unauthorized()

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": user.email,
            "iss": JWT_ISSUER,
            "iat": now,
            "exp": now + JWT_LIFETIME,
        },
        _configured_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )
    return TokenResponse(access_token=token)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> str:
    secret = _configured_jwt_secret()
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
        )
    except jwt.InvalidTokenError as error:
        raise _unauthorized() from error

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise _unauthorized()
    return subject
