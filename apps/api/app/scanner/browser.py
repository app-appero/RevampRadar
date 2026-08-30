import json
from pathlib import Path

from app.config import Settings

DESKTOP_VIEWPORT = (1440, 900)
MOBILE_VIEWPORT = (390, 844)

SHOT_LABELS = {
    "desktop": "Desktop",
    "mobile": "Mobile",
    "desktop_hero": "Desktop · inizio",
    "desktop_mid": "Desktop · contenuto",
    "desktop_footer": "Desktop · footer",
    "mobile_hero": "Mobile · inizio",
    "mobile_mid": "Mobile · contenuto",
    "preview_desktop": "Anteprima miglioramenti",
}

PREVIEW_STYLE = """
html { font-size: 18px !important; }
body { line-height: 1.5 !important; }
a, button, [role="button"] { min-height: 44px; }
[data-revampradar-preview="bar"] {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2147483646;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px;
  background: #1c1917;
  color: #fff;
  font-family: system-ui, sans-serif;
  box-shadow: 0 -8px 24px rgba(0,0,0,.2);
}
[data-revampradar-preview="bar"] strong { font-size: 16px; }
[data-revampradar-preview="bar"] span { font-size: 13px; opacity: .8; }
[data-revampradar-preview="bar"] em {
  font-style: normal;
  background: #fafaf9;
  color: #1c1917;
  padding: 8px 14px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
}
"""

COOKIE_SELECTORS = (
    "#onetrust-banner-sdk",
    "#CybotCookiebotDialog",
    ".cc-window",
    "#cookie-banner",
    ".cookie-banner",
    "[id='cookieConsent']",
)


def shot_label(device: str) -> str:
    return SHOT_LABELS.get(device, device.replace("_", " "))


def is_preview_shot(device: str) -> bool:
    return device.startswith("preview_")


def viewport_scroll_offsets(scroll_height: int, view_height: int) -> list[tuple[str, int]]:
    shots = [("hero", 0)]
    if view_height <= 0:
        return shots
    if scroll_height > int(view_height * 1.35):
        shots.append(("mid", view_height))
    if scroll_height > int(view_height * 2.2):
        shots.append(("footer", max(scroll_height - view_height, view_height * 2)))
    return shots


def capture_screenshots(url: str, output_dir: Path, settings: Settings) -> dict:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict = {"ok": True, "screenshots": [], "performance": {}, "error": None}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )
            try:
                desktop = _capture_device(
                    browser,
                    url,
                    output_dir,
                    "desktop",
                    DESKTOP_VIEWPORT,
                    settings,
                    with_preview=True,
                )
                mobile = _capture_device(
                    browser,
                    url,
                    output_dir,
                    "mobile",
                    MOBILE_VIEWPORT,
                    settings,
                    with_preview=False,
                )
                result["screenshots"] = desktop["screenshots"] + mobile["screenshots"]
                result["performance"] = desktop.get("performance") or {}
            finally:
                browser.close()
    except PlaywrightTimeout:
        result["ok"] = False
        result["error"] = "timeout"
    except Exception as exc:  # noqa: BLE001 - browser is best-effort
        result["ok"] = False
        result["error"] = str(exc) or "browser_error"
    return result


def _capture_device(
    browser,
    url: str,
    output_dir: Path,
    prefix: str,
    viewport: tuple[int, int],
    settings: Settings,
    with_preview: bool,
) -> dict:
    width, height = viewport
    page = browser.new_page(
        viewport={"width": width, "height": height},
        user_agent=settings.scanner_user_agent,
    )
    shots: list[dict] = []
    performance = None
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=settings.browser_timeout_ms)
        page.wait_for_timeout(500)
        scroll_height = int(page.evaluate("() => document.documentElement.scrollHeight") or height)
        for name, top in viewport_scroll_offsets(scroll_height, height):
            if prefix == "mobile" and name == "footer":
                continue
            page.evaluate(f"window.scrollTo(0, {top})")
            page.wait_for_timeout(250)
            path = output_dir / f"{prefix}_{name}.png"
            page.screenshot(path=str(path), full_page=False)
            shots.append(_shot_meta(f"{prefix}_{name}", width, height, path))

        if shots:
            performance = page.evaluate(
                """() => {
                  const nav = performance.getEntriesByType('navigation')[0];
                  if (!nav) return null;
                  return {
                    load_time_ms: Math.round(nav.loadEventEnd),
                    dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd),
                    transfer_size: nav.transferSize || null
                  };
                }"""
            )

        if with_preview:
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(150)
            page.add_style_tag(content=PREVIEW_STYLE)
            page.evaluate(_preview_dom_script())
            page.wait_for_timeout(200)
            path = output_dir / "preview_desktop.png"
            page.screenshot(path=str(path), full_page=False)
            shots.append(_shot_meta("preview_desktop", width, height, path))
        return {"screenshots": shots, "performance": performance}
    finally:
        page.close()


def _shot_meta(device: str, width: int, height: int, path: Path) -> dict:
    return {
        "device": device,
        "viewport_width": width,
        "viewport_height": height,
        "file_path": str(path),
        "label": shot_label(device),
    }


def _preview_dom_script() -> str:
    selectors = json.dumps(list(COOKIE_SELECTORS))
    return f"""() => {{
  const hide = {selectors};
  for (const sel of hide) {{
    document.querySelectorAll(sel).forEach((el) => {{ el.style.setProperty('display', 'none', 'important'); }});
  }}
  if (document.querySelector('[data-revampradar-preview="bar"]')) return;
  const bar = document.createElement('div');
  bar.setAttribute('data-revampradar-preview', 'bar');
  bar.innerHTML = '<div><strong>Prenota / Contattaci</strong><span> CTA visibile · testo più leggibile</span></div><em>Contattaci</em>';
  document.body.appendChild(bar);
  document.body.style.paddingBottom = '72px';
}}"""
