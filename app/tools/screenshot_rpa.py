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


def apply_sac_filter(page, filter_field: str, filter_value: str):
    """
    Vision-guided SAC filter interaction.
    Asks GPT-4o to locate UI elements by screenshot, then clicks by pixel coordinates.
    Best-effort: silently skips on any failure.
    """
    try:
        from app.agent import ask_vision_for_click
        tmp_dir = Path('output/screenshots')
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = str(tmp_dir / f'_filter_tmp_{int(time.time())}.png')

        # Step 1: find and click the filter chip
        page.screenshot(path=tmp, full_page=False)
        coords = ask_vision_for_click(
            tmp,
            f'Locate the filter chip or dropdown labeled "{filter_field}" in this SAP Analytics Cloud dashboard. '
            f'Return the center pixel coordinates (x, y) of that element.'
        )
        if not coords:
            return
        page.mouse.click(coords[0], coords[1])
        time.sleep(1.5)

        # Step 2: find and click the target value in the opened dropdown
        page.screenshot(path=tmp, full_page=False)
        coords2 = ask_vision_for_click(
            tmp,
            f'In this filter dropdown / panel, locate the option or radio button labeled "{filter_value}". '
            f'Return the center pixel coordinates (x, y) of that option.'
        )
        if coords2:
            page.mouse.click(coords2[0], coords2[1])
            time.sleep(1)

        # Step 3: look for a confirm button (OK / Apply / 确定)
        page.screenshot(path=tmp, full_page=False)
        coords3 = ask_vision_for_click(
            tmp,
            'Is there an OK, Apply, or Confirm button visible in this screenshot? '
            'If yes, return its center pixel coordinates (x, y). If not, return null.'
        )
        if coords3:
            page.mouse.click(coords3[0], coords3[1])
            time.sleep(0.5)

        # Step 4: dismiss dropdown with Escape only — do NOT click anywhere (risks SAP nav)
        page.keyboard.press("Escape")
        time.sleep(0.3)
        page.keyboard.press("Escape")  # double-press in case first was swallowed
        time.sleep(1.5)

        # Clean up temp file
        try:
            import os as _os
            _os.remove(tmp)
        except Exception:
            pass

        time.sleep(2)
    except Exception:
        pass


def take_screenshot(url: str, output_path: str | None = None) -> str:
    """Take a single screenshot (first page). Returns path."""
    paths = take_screenshots(url)
    return paths[0]


def take_screenshots(url: str, filter_field: str = "", filter_value: str = "") -> list[str]:
    """Take screenshots of all pages in a SAC Story. Returns list of paths.
    If filter_field and filter_value are given, applies the SAC filter first and returns only one page."""
    if not SESSION_FILE.exists():
        raise RuntimeError("No SAC session found. Please run the login flow first.")

    ts = int(time.time())

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
            headless=False,
            args=["--start-maximized"],
        )
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            storage_state=str(SESSION_FILE),
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        page.goto(url, wait_until="commit", timeout=120000)

        current_url = page.url
        if any(k in current_url for k in ["login", "signin", "sso", "authentication", "logon"]):
            browser.close()
            clear_session()
            raise RuntimeError("SESSION_EXPIRED")

        def _wait_for_charts():
            # 1. 等加载屏消失
            try:
                page.wait_for_selector(
                    "[class*='loadingScreen'], [class*='loading-screen'], [class*='splashScreen']",
                    state="hidden", timeout=60000,
                )
            except Exception:
                pass
            # 2. 等 SAP UI 元素出现
            try:
                page.wait_for_selector(
                    "canvas, [class*=sapUiBody], [data-sap-ui], [class*=v-VizFrame], svg",
                    timeout=60000,
                )
            except Exception:
                pass
            # 3. 等网络空闲（图表数据请求完成）
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            # 4. 等 canvas 真正画满（有色彩像素，不是全灰骨架）
            try:
                page.wait_for_function(
                    """() => {
                        const bodyText = document.body.innerText || '';
                        const isLoading = bodyText.includes('Loading your story')
                            || bodyText.includes('Loading...')
                            || bodyText.includes('Redirecting');
                        if (isLoading) return false;

                        const canvases = Array.from(document.querySelectorAll('canvas'));
                        if (canvases.length === 0) return false;

                        // 检查至少一个大 canvas 里有非灰色像素（图表真正渲染完）
                        const rendered = canvases.filter(c => c.width > 200 && c.height > 100).some(c => {
                            try {
                                const ctx = c.getContext('2d');
                                if (!ctx) return false;
                                const d = ctx.getImageData(0, 0, Math.min(c.width, 400), Math.min(c.height, 400)).data;
                                for (let i = 0; i < d.length; i += 16) {
                                    const r = d[i], g = d[i+1], b = d[i+2], a = d[i+3];
                                    if (a > 0 && !(r > 190 && g > 190 && b > 190)) return true; // 非灰非白像素
                                }
                                return false;
                            } catch(e) { return true; } // cross-origin 报错视为已渲染
                        });
                        return rendered;
                    }""",
                    timeout=120000,
                )
            except Exception:
                pass
            # 5. 额外静候，让动画收尾
            time.sleep(8)
            # 6. 关闭可能残留的弹窗
            try:
                page.evaluate("""() => {
                    document.querySelectorAll(
                        '.sapMDialog, .sapMPopover, .sapMPopup, .sapUiBlockLayer, .sapMBlockLayerOnly'
                    ).forEach(e => e.remove());
                }""")
            except Exception:
                pass
            time.sleep(0.5)

        paths = []
        filter_mode = bool(filter_field and filter_value)

        _wait_for_charts()

        if filter_mode:
            # 筛选器模式：应用 filter 后只截当前页
            original_url = page.url
            apply_sac_filter(page, filter_field, filter_value)
            if page.url != original_url and "story" not in page.url.lower():
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
            time.sleep(3)
            _wait_for_charts()
            out = str(SCREENSHOT_DIR / f"screenshot_{ts}_p1.png")
            page.screenshot(path=out, full_page=False)
            paths.append(out)
        else:
            # 无筛选器模式：只截当前页（用户传入的 URL 即目标页）
            out = str(SCREENSHOT_DIR / f"screenshot_{ts}_p1.png")
            page.screenshot(path=out, full_page=False)
            paths.append(out)

        browser.close()

    return paths
