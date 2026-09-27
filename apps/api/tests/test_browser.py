import inspect

from app.scanner import browser
from app.scanner.browser import capture_screenshots, shot_label, viewport_scroll_offsets


def test_viewport_scroll_offsets_short_page() -> None:
    assert viewport_scroll_offsets(800, 900) == [("hero", 0)]


def test_viewport_scroll_offsets_medium_page() -> None:
    shots = viewport_scroll_offsets(1400, 900)
    assert [name for name, _ in shots] == ["hero", "mid"]
    assert shots[1][1] == 900


def test_viewport_scroll_offsets_long_page() -> None:
    shots = viewport_scroll_offsets(3000, 900)
    assert [name for name, _ in shots] == ["hero", "mid", "footer"]
    assert shots[2][1] == 2100


def test_shot_labels() -> None:
    assert shot_label("desktop_hero") == "Desktop · inizio"
    assert shot_label("mobile_mid") == "Mobile · contenuto"


def test_no_preview_labels_left() -> None:
    assert not any(key.startswith("preview_") for key in browser.SHOT_LABELS)
    assert not any("Dopo" in value for value in browser.SHOT_LABELS.values())


def test_preview_generation_removed_from_module() -> None:
    # Nessuna anteprima "dopo" artificiale: solo screenshot reali, senza flag di controllo.
    assert not hasattr(browser, "is_preview_shot")
    assert not hasattr(browser, "PREVIEW_STYLE")
    assert not hasattr(browser, "COOKIE_SELECTORS")
    assert "with_preview" not in inspect.signature(capture_screenshots).parameters
