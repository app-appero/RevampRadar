import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse


class UrlValidationError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedUrl:
    original: str
    normalized: str
    domain: str
    scheme: str


def normalize_url(raw: str) -> NormalizedUrl:
    original = raw.strip()
    if not original:
        raise UrlValidationError("Inserisci un URL.")
    if len(original) > 2048:
        raise UrlValidationError("L'URL è troppo lungo.")

    candidate = original if "://" in original else f"https://{original}"
    parsed = urlparse(candidate)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UrlValidationError("Sono ammessi solo URL http o https.")

    hostname = parsed.hostname
    if not hostname:
        raise UrlValidationError("L'URL non contiene un dominio valido.")
    if _is_blocked_literal_host(hostname):
        raise UrlValidationError("Non è possibile analizzare indirizzi di rete privati o locali.")

    try:
        domain = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UrlValidationError("Il dominio non è valido.") from exc

    port = parsed.port
    netloc = domain
    if port and port not in {80, 443}:
        netloc = f"{domain}:{port}"

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    normalized = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    return NormalizedUrl(original=original, normalized=normalized, domain=domain, scheme=scheme)


_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


def _is_blocked_literal_host(hostname: str) -> bool:
    """Rifiuta gli indirizzi IP letterali privati/locali (SSRF di base).

    Non risolve i nomi a dominio qui (resterebbe una funzione pura, senza rete):
    la verifica sull'IP effettivamente raggiunto avviene allo scan (vedi scanner/http.py),
    così anche un dominio pubblico che punta a un IP privato viene bloccato prima di
    essere interrogato o fotografato.
    """
    host = hostname.strip().lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES:
        return True
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        parsed_ip.is_private
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_multicast
        or parsed_ip.is_reserved
        or parsed_ip.is_unspecified
    )
