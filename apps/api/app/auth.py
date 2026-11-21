from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time

from starlette.datastructures import MutableHeaders
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Le immagini degli screenshot sono caricate da <img src>, che non può inviare header:
# restano raggiungibili senza credenziali (UUID non indovinabile, solo pagine pubbliche).
_OPEN_PATHS = (re.compile(r"^/health$"), re.compile(r"^/audits/[0-9a-fA-F-]{36}/screenshots/[a-z]+$"))

SESSION_COOKIE = "rr_session"
# Schema non interattivo: i browser mostrano la finestra di login solo per Basic/Digest/NTLM/
# Negotiate. Così una fetch senza credenziali riceve subito il 401 invece di restare appesa.
API_CHALLENGE = 'xBasic realm="RevampRadar"'
BROWSER_CHALLENGE = 'Basic realm="RevampRadar"'
_API_MESSAGE = (
    "Autenticazione richiesta: sessione assente o scaduta. Apri una pagina dell'API nel browser "
    "per accedere di nuovo, oppure invia l'header Authorization: Basic."
)


def is_api_request(headers: dict[bytes, bytes]) -> bool:
    """True per fetch/XHR e client JSON: niente finestra di login, solo un 401 leggibile.

    Si usa la finestra Basic solo per una pagina aperta dalla barra degli indirizzi
    (Sec-Fetch-Mode: navigate) o per client senza questi segnali (es. curl).
    """
    if headers.get(b"x-requested-with"):
        return True
    mode = headers.get(b"sec-fetch-mode", b"").decode("latin-1").strip().lower()
    dest = headers.get(b"sec-fetch-dest", b"").decode("latin-1").strip().lower()
    if mode == "navigate" or dest in {"document", "iframe", "frame"}:
        return False
    if mode or dest == "empty":
        return True  # fetch()/XHR: cors, same-origin, no-cors
    accept = headers.get(b"accept", b"").decode("latin-1").lower()
    return "application/json" in accept and "text/html" not in accept


class BasicAuthMiddleware:
    """HTTP Basic opzionale: attivo solo se username e password sono configurati.

    Dopo un accesso Basic valido emette un cookie di sessione firmato (HttpOnly, Secure,
    SameSite=Strict) che vale per tutti i percorsi e dura più della sessione Basic del browser.
    """

    def __init__(self, app: ASGIApp, username: str, password: str, session_hours: float = 0) -> None:
        self.app = app
        self._expected = f"{username}:{password}".encode()
        # La chiave dipende dalle credenziali: cambiare password invalida le sessioni aperte.
        self._key = hashlib.sha256(b"revampradar-session\x00" + self._expected).digest()
        self._session_seconds = int(max(0.0, session_hours) * 3600)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS" or self._is_open(scope):
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        if authorization.lower().startswith("basic ") and self._valid(authorization[6:].strip()):
            await self.app(scope, receive, self._with_session_cookie(send, headers))
            return
        if self._session_ok(headers):
            await self.app(scope, receive, send)
            return
        await self._unauthorized(headers)(scope, receive, send)

    @staticmethod
    def _is_open(scope: Scope) -> bool:
        return scope["method"] == "GET" and any(p.match(scope["path"]) for p in _OPEN_PATHS)

    def _valid(self, token: str) -> bool:
        try:
            decoded = base64.b64decode(token, validate=True)
        except ValueError:
            return False
        return secrets.compare_digest(decoded, self._expected)

    @staticmethod
    def _unauthorized(headers: dict[bytes, bytes]) -> Response:
        vary = "Accept, Sec-Fetch-Mode, Sec-Fetch-Dest, X-Requested-With"
        if is_api_request(headers):
            return Response(
                json.dumps({"detail": _API_MESSAGE, "code": "auth_required"}, ensure_ascii=False),
                status_code=401,
                media_type="application/json",
                headers={"WWW-Authenticate": API_CHALLENGE, "Cache-Control": "no-store", "Vary": vary},
            )
        return PlainTextResponse(
            "Autenticazione richiesta.",
            status_code=401,
            headers={"WWW-Authenticate": BROWSER_CHALLENGE, "Cache-Control": "no-store", "Vary": vary},
        )

    # --- cookie di sessione ---------------------------------------------------------------

    def _sign(self, expires: int) -> str:
        return hmac.new(self._key, str(expires).encode(), hashlib.sha256).hexdigest()

    def session_token(self, now: float | None = None) -> str:
        expires = int(now if now is not None else time.time()) + self._session_seconds
        return f"{expires}.{self._sign(expires)}"

    def _session_expiry(self, headers: dict[bytes, bytes]) -> int | None:
        if not self._session_seconds:
            return None
        raw = headers.get(b"cookie", b"").decode("latin-1")
        for chunk in raw.split(";"):
            name, _, value = chunk.strip().partition("=")
            if name != SESSION_COOKIE:
                continue
            expires_text, _, signature = value.partition(".")
            if not expires_text.isdigit() or not secrets.compare_digest(signature, self._sign(int(expires_text))):
                return None
            return int(expires_text)
        return None

    def _session_ok(self, headers: dict[bytes, bytes]) -> bool:
        expires = self._session_expiry(headers)
        return expires is not None and expires > time.time()

    def _with_session_cookie(self, send: Send, headers: dict[bytes, bytes]) -> Send:
        if not self._session_seconds:
            return send
        expires = self._session_expiry(headers)
        # Rinnovo solo se manca o ha consumato metà della durata: niente Set-Cookie a ogni chiamata.
        if expires is not None and expires - time.time() > self._session_seconds / 2:
            return send
        cookie = (
            f"{SESSION_COOKIE}={self.session_token()}; Max-Age={self._session_seconds}; Path=/; "
            "HttpOnly; Secure; SameSite=Strict"
        )

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).append("set-cookie", cookie)
            await send(message)

        return send_with_cookie
