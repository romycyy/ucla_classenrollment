import os
import subprocess
import sys
import time
import urllib.request
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

load_dotenv()

LOGIN_URL = os.getenv("LOGIN_URL", "https://example.com/login")
USERNAME = os.getenv("BOT_USERNAME")
PASSWORD = os.getenv("BOT_PASSWORD")
CHROME_DEBUGGING_PORT = os.getenv("CHROME_DEBUGGING_PORT")

# Chrome requires a *non-default* --user-data-dir when using remote debugging.
# Use a separate profile so debugging works; log in once in that window, cookies persist.
CHROME_DEBUG_PROFILE = os.path.expanduser("~/.chrome-remote-debug")

# Paths to Chrome for auto-launch (only used when connecting fails)
_CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",   # Windows
]


def _launch_chrome_for_debugging(port: str) -> bool:
    """Start Chrome with a separate profile and remote debugging. Returns True if launched."""
    profile = os.path.expanduser(CHROME_DEBUG_PROFILE)
    for exe in _CHROME_PATHS:
        if os.path.exists(exe):
            try:
                subprocess.Popen(
                    [exe, f"--user-data-dir={profile}", f"--remote-debugging-port={port}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception:
                continue
            return True
    return False


def _wait_for_debug_port(port: str, timeout_sec: float = 30) -> bool:
    """Return True when the debug port responds."""
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Set BOT_USERNAME and BOT_PASSWORD env vars before running.")

    with sync_playwright() as p:
        context = None
        page = None
        browser = None
        we_own_browser = (
            True  # False when connecting to existing Chrome (don't close it)
        )

        if CHROME_DEBUGGING_PORT:
            # Connect to Chrome (start it automatically if not running)
            port = CHROME_DEBUGGING_PORT
            cdp_url = f"http://127.0.0.1:{port}"
            try:
                browser = p.chromium.connect_over_cdp(cdp_url, timeout=5000)
            except Exception:
                print("Chrome not detected on port", port, "- launching Chrome...", file=sys.stderr)
                if _launch_chrome_for_debugging(port) and _wait_for_debug_port(port):
                    browser = p.chromium.connect_over_cdp(cdp_url, timeout=10000)
                else:
                    try:
                        browser = p.chromium.connect_over_cdp(cdp_url, timeout=5000)
                    except Exception as e:
                        print(
                            "Could not connect. Start Chrome manually:\n"
                            '  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --user-data-dir="{}" --remote-debugging-port={}\n'
                            "Error: {}".format(CHROME_DEBUG_PROFILE, port, e),
                            file=sys.stderr,
                        )
                        raise SystemExit(1) from e
            we_own_browser = False
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
        else:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

        try:
            page.goto(LOGIN_URL, wait_until="load", timeout=30000)

            # Click "Sign in" on the landing page to go to the login page
            signin_clicked = False

            try:
                page.get_by_role("link", name="Sign In").first.click(timeout=1000)
                signin_clicked = True
            except Exception:
                try:
                    page.get_by_role("button", name="Sign in").first.click(timeout=1000)
                    signin_clicked = True
                except Exception:
                    pass

            if not signin_clicked:
                raise RuntimeError(
                    'Could not find "Sign in" (or similar) on the page. Check the button/link text.'
                )
            # Wait for redirect to login page and for the login form to appear
            page.wait_for_selector(
                "input[type='password']", state="visible", timeout=10000
            )

            # --- Fill username: try common labels/placeholders, then fallback to first text/email input ---
            username_filled = False
            for label in ("Email", "Username", "邮箱", "手机号", "Email address"):
                try:
                    page.get_by_label(label).first.fill(USERNAME, timeout=1000)
                    username_filled = True
                    break
                except Exception:
                    continue
            if not username_filled:
                try:
                    page.locator("input[type='email']").first.fill(
                        USERNAME, timeout=1000
                    )
                    username_filled = True
                except Exception:
                    page.locator("input[type='text']").first.fill(
                        USERNAME, timeout=1000
                    )
                    username_filled = True
            if not username_filled:
                raise RuntimeError(
                    "Could not find username/email field. Check the page or add the right selector."
                )

            # --- Fill password: label or type=password ---
            try:
                page.get_by_label("Password").first.fill(PASSWORD, timeout=3000)
            except Exception:
                page.locator("input[type='password']").first.fill(
                    PASSWORD, timeout=1000
                )

            # --- Click login ---
            for btn_name in ("Log in", "Login", "登录", "Sign in"):
                try:
                    page.get_by_role("button", name=btn_name).first.click(timeout=1000)
                    break
                except Exception:
                    continue
            else:
                page.locator("button[type='submit'], input[type='submit']").first.click(
                    timeout=1000
                )

            print("✅ Logged in and clicked Profile")

        except PWTimeout:
            page.screenshot(path="error.png", full_page=True)
            print("❌ Timed out. Saved screenshot to error.png")
            raise
        finally:
            if we_own_browser and context:
                context.close()
            if we_own_browser and browser:
                browser.close()


if __name__ == "__main__":
    main()
