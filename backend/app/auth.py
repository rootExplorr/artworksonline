import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, Request, status
from pwdlib import PasswordHash

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

COOKIE_NAME = "arton_admin_session"
COOKIE_PATH = "/api"
TOKEN_LIFETIME = timedelta(hours=8)
TOKEN_ISSUER = "artonline-api"
FRONTEND_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:4200").split(",")
    if origin.strip()
)
password_hasher = PasswordHash.recommended()


@dataclass(frozen=True)
class AdminSettings:
    username: str
    password_hash: str
    signing_secret: str
    cookie_secure: bool


def get_admin_settings() -> AdminSettings:
    username = os.getenv("ADMIN_USERNAME")
    password_hash = os.getenv("ADMIN_PASSWORD_HASH")
    signing_secret = os.getenv("AUTH_SECRET_KEY")
    if not username or not password_hash or not signing_secret or len(signing_secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured.",
        )
    return AdminSettings(
        username=username,
        password_hash=password_hash,
        signing_secret=signing_secret,
        cookie_secure=os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true",
    )


def validate_request_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and not any(secrets.compare_digest(origin, allowed) for allowed in FRONTEND_ORIGINS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Request origin is not allowed.")


def verify_admin_credentials(username: str, password: str, settings: AdminSettings) -> bool:
    try:
        password_valid = password_hasher.verify(password, settings.password_hash)
    except Exception:
        password_valid = False
    return secrets.compare_digest(username, settings.username) and password_valid


def create_admin_token(settings: AdminSettings) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": settings.username,
            "iss": TOKEN_ISSUER,
            "iat": now,
            "exp": now + TOKEN_LIFETIME,
        },
        settings.signing_secret,
        algorithm="HS256",
    )


def require_admin(request: Request) -> str:
    validate_request_origin(request)
    settings = get_admin_settings()
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin login required.",
        )
    try:
        payload = jwt.decode(
            token,
            settings.signing_secret,
            algorithms=["HS256"],
            issuer=TOKEN_ISSUER,
            options={"require": ["exp", "iat", "iss", "sub"]},
        )
    except jwt.InvalidTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session is invalid or expired.",
        ) from error
    if payload.get("sub") != settings.username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin session is invalid.")
    return settings.username