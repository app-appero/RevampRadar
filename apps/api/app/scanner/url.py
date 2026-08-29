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
