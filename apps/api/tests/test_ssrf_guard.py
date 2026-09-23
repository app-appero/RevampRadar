import socket

import httpx

from app.config import Settings
from app.scanner.http import _reject_private_targets, scan_http
from app.scanner.ssrf_guard import is_public_hostname


def _fake_getaddrinfo(ip: str):
    def _inner(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return _inner


def _fake_getaddrinfo_by_host(mapping: dict[str, str]):
    def _inner(host, port, *args, **kwargs):
        ip = mapping[host]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return _inner


def test_public_hostname_true_for_public_ip(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    assert is_public_hostname("example.com") is True


def test_public_hostname_false_for_private_ip(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.5"))
    assert is_public_hostname("internal.example") is False


def test_public_hostname_false_when_unresolvable(monkeypatch) -> None:
    def _raise(host, port, *args, **kwargs):
        raise socket.gaierror("not found")

    monkeypatch.setattr(socket, "getaddrinfo", _raise)
    assert is_public_hostname("doesnotexist.invalid") is False


def test_scan_http_blocks_domain_resolving_to_private_ip(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
    settings = Settings()
    result = scan_http("https://looks-public-but-isnt.test", settings)
    assert result.ok is False
    assert result.error == "blocked_private_target"


def test_scan_http_blocks_redirect_to_private_ip(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "public.test":
            return httpx.Response(302, headers={"Location": "http://internal.test/secret"})
        raise AssertionError("should never reach the redirect target")

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_by_host({"public.test": "93.184.216.34", "internal.test": "127.0.0.1"}),
    )
    transport = httpx.MockTransport(handler)
    client = httpx.Client(
        transport=transport,
        follow_redirects=True,
        event_hooks={"request": [_reject_private_targets]},
    )
    settings = Settings()
    result = scan_http("http://public.test", settings, client=client)
    assert result.ok is False
    assert result.error == "blocked_private_target"
