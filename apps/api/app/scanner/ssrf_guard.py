from __future__ import annotations

import ipaddress
import socket

_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


class SSRFBlockedError(RuntimeError):
    """L'host risolve (o è) un indirizzo di rete privato/locale: richiesta bloccata."""


def is_public_hostname(hostname: str) -> bool:
    """Vero se l'host è raggiungibile solo su IP pubblici (nessuno privato/loopback/locale).

    Risolve il DNS: un host che non risolve affatto non è considerato pubblico (verrà
    comunque intercettato più avanti come normale errore di connessione).
    """
    host = (hostname or "").strip().lower().rstrip(".")
    if not host or host in _BLOCKED_HOSTNAMES:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        address = info[4][0]
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            return False
        if (
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_multicast
            or parsed.is_reserved
            or parsed.is_unspecified
        ):
            return False
    return True
