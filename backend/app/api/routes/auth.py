from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth import (
    COOKIE_NAME,
    COOKIE_PATH,
    TOKEN_LIFETIME,
    create_admin_token,
    get_admin_settings,
    require_admin,
    validate_request_origin,
    verify_admin_credentials,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    authenticated: bool
    username: str


@router.post("/login", response_model=SessionResponse)
def login(credentials: LoginRequest, request: Request, response: Response) -> SessionResponse:
    validate_request_origin(request)
    settings = get_admin_settings()
    if not verify_admin_credentials(credentials.username, credentials.password, settings):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    response.set_cookie(
        key=COOKIE_NAME,
        value=create_admin_token(settings),
        max_age=int(TOKEN_LIFETIME.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )
    return SessionResponse(authenticated=True, username=settings.username)


@router.get("/session", response_model=SessionResponse)
def session(username: str = Depends(require_admin)) -> SessionResponse:
    return SessionResponse(authenticated=True, username=username)


@router.post("/logout", status_code=204, response_class=Response)
def logout(request: Request, response: Response) -> Response:
    validate_request_origin(request)
    settings = get_admin_settings()
    response.delete_cookie(
        key=COOKIE_NAME,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response