"""Stato della sessione, login e logout per l'uso da browser e dalle routine automatiche."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.auth import SESSION_COOKIE

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatus(BaseModel):
    auth_enabled: bool
    authenticated: bool
    method: str | None = Field(default=None, description="basic, cookie oppure null.")
    session: str = Field(description="valid, expired, invalid, missing oppure disabled.")
    expires_at: datetime | None = None
    seconds_left: int | None = None
    session_days: float | None = None
    renewal: str = "Ogni richiesta autenticata rinnova la scadenza (al più un nuovo cookie all'ora)."
    login_url: str = "/auth/login"


def _status(request: Request) -> AuthStatus:
    info = getattr(request.state, "auth", None)
    if not info:
        return AuthStatus(auth_enabled=False, authenticated=True, session="disabled")
    expires = info.get("expires_at")
    seconds = info.get("session_seconds") or 0
    return AuthStatus(
        auth_enabled=True,
        authenticated=bool(info.get("authenticated")),
        method=info.get("method"),
        session=info.get("session") or "missing",
        expires_at=datetime.fromtimestamp(expires, UTC) if expires else None,
        seconds_left=max(0, int(expires - time.time())) if expires else None,
        session_days=round(seconds / 86400, 2) if seconds else None,
    )


@router.get(
    "/status",
    response_model=AuthStatus,
    summary="La sessione è valida? Quando scade?",
    description=(
        "Risponde sempre 200, anche senza sessione: `authenticated` dice se le altre chiamate passano, "
        "`expires_at`/`seconds_left` quando scade il cookie. Non rinnova la sessione. Se "
        "`authenticated` è false apri `login_url` nel browser (finestra di accesso) e riprova."
    ),
)
def get_auth_status(request: Request) -> AuthStatus:
    return _status(request)


@router.get(
    "/login",
    response_model=AuthStatus,
    summary="Accesso: crea o rinnova il cookie di sessione",
    description=(
        "Da aprire nel browser: senza sessione chiede le credenziali (finestra Basic), poi emette il cookie "
        "`rr_session` di lunga durata. Con `next=/percorso` (stesso sito) reindirizza lì dopo l'accesso. "
        "Una fetch con header Authorization: Basic ottiene lo stesso cookie."
    ),
)
def get_auth_login(request: Request, next: str | None = Query(default=None, max_length=512)):  # noqa: A002
    if next and next.startswith("/") and not next.startswith("//") and "\\" not in next:
        return RedirectResponse(next, status_code=303)
    return _status(request)


@router.post("/logout", summary="Esci: cancella il cookie di sessione")
def post_auth_logout() -> JSONResponse:
    response = JSONResponse({"logged_out": True})
    response.set_cookie(SESSION_COOKIE, "", max_age=0, path="/", secure=True, httponly=True, samesite="strict")
    return response
