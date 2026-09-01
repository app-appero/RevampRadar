from app.scanner.browser import is_preview_shot, shot_label, viewport_scroll_offsets


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
    assert shot_label("preview_desktop_hero") == "Dopo · desktop inizio"
    assert is_preview_shot("preview_desktop_hero")
    assert not is_preview_shot("desktop_hero")
