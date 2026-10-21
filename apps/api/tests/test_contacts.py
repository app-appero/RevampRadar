from types import SimpleNamespace

from app.config import Settings
from app.discovery.contacts import extract_public_email


def test_extract_public_email_from_same_origin_contact_page(monkeypatch) -> None:
    from app.discovery import contacts

    pages = {
        "https://business.test/": """
            <a href="https://other.test/contact">Contatti</a>
            <a href="/contatti">Contatti</a>
        """,
        "https://business.test/contatti": """
            <a href="mailto:INFO@business.test?subject=hello">Scrivici</a>
        """,
    }
    requested: list[str] = []

    def fake_scan_http(url: str, settings: Settings):
        requested.append(url)
        return SimpleNamespace(ok=True, html=pages[url], final_url=url)

    monkeypatch.setattr(contacts, "scan_http", fake_scan_http)

    email = extract_public_email(Settings(), "https://business.test/")

    assert email == "info@business.test"
    assert requested == ["https://business.test/", "https://business.test/contatti"]


def test_extract_public_email_ignores_example_addresses(monkeypatch) -> None:
    from app.discovery import contacts

    monkeypatch.setattr(
        contacts,
        "scan_http",
        lambda url, settings: SimpleNamespace(
            ok=True,
            html="<p>info@example.com</p>",
            final_url=url,
        ),
    )

    assert extract_public_email(Settings(), "https://business.test/") is None
