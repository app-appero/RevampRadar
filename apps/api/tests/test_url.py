import pytest

from app.scanner.url import UrlValidationError, normalize_url


def test_normalize_adds_https_and_lowercases_host() -> None:
    result = normalize_url("Example.COM/Path/")
    assert result.normalized == "https://example.com/Path"
    assert result.domain == "example.com"


def test_normalize_keeps_query_and_drops_fragment() -> None:
    result = normalize_url("https://example.com/a/?q=1#section")
    assert result.normalized == "https://example.com/a?q=1"


def test_reject_empty() -> None:
    with pytest.raises(UrlValidationError):
        normalize_url("  ")


def test_reject_non_http_scheme() -> None:
    with pytest.raises(UrlValidationError):
        normalize_url("ftp://example.com")


@pytest.mark.parametrize(
    "raw",
    [
        "http://127.0.0.1",
        "http://localhost",
        "http://localhost:8000",
        "http://192.168.1.10",
        "http://10.0.0.5/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]",
    ],
)
def test_reject_private_or_local_literal_targets(raw: str) -> None:
    with pytest.raises(UrlValidationError):
        normalize_url(raw)


def test_public_ip_literal_is_allowed() -> None:
    result = normalize_url("http://93.184.216.34")
    assert result.domain == "93.184.216.34"
