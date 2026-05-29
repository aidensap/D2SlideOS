import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SESSION_FILE = Path("rpa_session.json")
SCREENSHOT_DIR = Path("output/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def has_session() -> bool:
    return SESSION_FILE.exists()


def clear_session():
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def login_interactive(url: str) -> bool:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless=False, slow_mo=50)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        try:
            page.wait_for_selector(
                "[id*=sapui5], [class*=sapUiBody], canvas, [data-sap-ui]",
                timeout=180000,
            )
        except Exception:
            pass

        time.sleep(3)

        # Save full browser state: cookies + localStorage + sessionStorage
        ctx.storage_state(path=str(SESSION_FILE))
        browser.close()
    return True


def take_screenshot(url: str, output_path: str | None = None) -> str:
    if not SESSION_FILE.exists():
        raise RuntimeError("No SAC session found. Please run the login flow first.")

    if output_path is None:
        ts = int(time.time())
        output_path = str(SCREENSHOT_DIR / f"screenshot_{ts}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
            headless=False,
            args=["--start-maximized"],
        )
        # Restore full browser state from saved session
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 900},
            storage_state=str(SESSION_FILE),
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=90000)

        # Detect redirect to login page (session expired)
        current_url = page.url
        if any(k in current_url for k in ["login", "signin", "sso", "authentication", "logon"]):
            browser.close()
            clear_session()
            raise RuntimeError("SESSION_EXPIRED")

        # Wait for loading screen to disappear
        try:
            page.wait_for_selector(
                "[class*='loadingScreen'], [class*='loading-screen'], [class*='splashScreen']",
                state="hidden",
                timeout=60000,
            )
        except Exception:
            pass

        # Wait for SAC UI shell
        try:
            page.wait_for_selector(
                "canvas, [class*=sapUiBody], [data-sap-ui], [class*=v-VizFrame], svg",
                timeout=60000,
            )
        except Exception:
            pass

        # Wait for charts to render AND loading screen to be gone
        try:
            page.wait_for_function(
                """() => {
                    // Must have real canvas elements
                    const canvases = Array.from(document.querySelectorAll('canvas'));
                    const hasCharts = canvases.length > 0 && canvases.some(c => c.width > 200 && c.height > 100);
                    // Must not have loading text on screen
                    const bodyText = document.body.innerText || '';
                    const isLoading = bodyText.includes('Loading your story') || bodyText.includes('Loading...');
                    return hasCharts && !isLoading;
                }""",
                timeout=120000,
            )
        except Exception:
            pass

        time.sleep(5)

        # Remove any dialogs/popups right before screenshotting
        page.evaluate("""() => {
            document.querySelectorAll(
                '.sapMDialog, .sapMPopover, .sapMPopup, .sapUiBlockLayer, .sapMBlockLayerOnly'
            ).forEach(e => e.remove());
        }""")
        time.sleep(0.5)
        page.screenshot(path=output_path, full_page=False)
        browser.close()

    return output_path
