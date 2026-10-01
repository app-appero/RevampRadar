from __future__ import annotations

import base64
import re
import secrets

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Le immagini degli screenshot sono caricate da <img src>, che non può inviare header:
# restano raggiungibili senza credenziali (UUID non indovinabile, solo pagine pubbliche).
_OPEN_PATHS = (re.compile(r"^/health$"), re.compile(r"^/audits/[0-9a-fA-F-]{36}/screenshots/[a-z]+$"))


class BasicAuthMiddleware:
    """HTTP Basic opzionale: attivo solo se username e password sono configurati."""

    def __init__(self, app: ASGIApp, username: str, password: str) -> None:
        self.app = app
        self._expected = f"{username}:{password}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS" or self._is_open(scope):
            await self.app(scope, receive, send)
            return
        header = dict(scope["headers"]).get(b"authorization", b"").decode()
        if header.lower().startswith("basic ") and self._valid(header[6:].strip()):
            await self.app(scope, receive, send)
            return
        response = PlainTextResponse(
            "Autenticazione richiesta.", status_code=401, headers={"WWW-Authenticate": 'Basic realm="RevampRadar"'}
        )
        await response(scope, receive, send)

    @staticmethod
    def _is_open(scope: Scope) -> bool:
        return scope["method"] == "GET" and any(p.match(scope["path"]) for p in _OPEN_PATHS)

    def _valid(self, token: str) -> bool:
        try:
            decoded = base64.b64decode(token, validate=True)
        except ValueError:
            return False
        return secrets.compare_digest(decoded, self._expected)
