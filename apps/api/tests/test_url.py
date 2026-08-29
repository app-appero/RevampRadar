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
