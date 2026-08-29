from pathlib import Path

from app.config import Settings

DESKTOP_VIEWPORT = (1440, 900)
MOBILE_VIEWPORT = (390, 844)


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
                desktop = _capture(browser, url, output_dir / "desktop.png", DESKTOP_VIEWPORT, settings)
                mobile = _capture(browser, url, output_dir / "mobile.png", MOBILE_VIEWPORT, settings)
                result["screenshots"] = [desktop, mobile]
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


def _capture(browser, url: str, path: Path, viewport: tuple[int, int], settings: Settings) -> dict:
    width, height = viewport
    page = browser.new_page(
        viewport={"width": width, "height": height},
        user_agent=settings.scanner_user_agent,
    )
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=settings.browser_timeout_ms)
        page.wait_for_timeout(500)
        page.screenshot(path=str(path), full_page=False)
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
        return {
            "device": "desktop" if width >= 1000 else "mobile",
            "viewport_width": width,
            "viewport_height": height,
            "file_path": str(path),
            "performance": performance,
        }
    finally:
        page.close()
