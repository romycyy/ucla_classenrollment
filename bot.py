import os
import sys
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

load_dotenv()

LOGIN_URL = os.getenv("LOGIN_URL", "https://example.com/login")
USERNAME = os.getenv("BOT_USERNAME")
PASSWORD = os.getenv("BOT_PASSWORD")
# Use your Chrome with cookies: set CHROME_DEBUGGING_PORT=9222 and start Chrome with:
#   macOS: /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
#   Windows: "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
CHROME_DEBUGGING_PORT = os.getenv("CHROME_DEBUGGING_PORT")
# Or use your Chrome profile by path (Chrome must be closed first):
#   macOS default: ~/Library/Application Support/Google/Chrome
CHROME_USER_DATA_DIR = os.getenv("CHROME_USER_DATA_DIR")


def main():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Set BOT_USERNAME and BOT_PASSWORD env vars before running.")

    with sync_playwright() as p:
        context = None
        page = None
        browser = None
        we_own_browser = True  # False when connecting to existing Chrome (don't close it)

        if CHROME_DEBUGGING_PORT:
            # Connect to your already-running Chrome (with your profile & cookies)
            try:
                browser = p.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{CHROME_DEBUGGING_PORT}",
                    timeout=5000,
                )
            except Exception as e:
                print(
                    "Could not connect to Chrome. Start Chrome with remote debugging first, e.g.:\n"
                    "  macOS:   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222\n"
                    "  Windows: \"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" --remote-debugging-port=9222\n",
                    file=sys.stderr,
                )
                raise SystemExit(1) from e
            we_own_browser = False
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
        elif CHROME_USER_DATA_DIR:
            # Launch Chrome with your profile (Chrome must be closed first)
            expanded = os.path.expanduser(CHROME_USER_DATA_DIR)
            context = p.chromium.launch_persistent_context(
                expanded,
                channel="chrome",
                headless=False,
                timeout=30000,
            )
            page = context.new_page()
            # persistent context: no separate browser ref, context.close() closes the window
        else:
            # Default: test Chromium, no profile
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

        try:
            page.goto(LOGIN_URL, wait_until="load", timeout=30000)

            # Click "Sign in" on the landing page to go to the login page
            signin_clicked = False
            for name in ("Sign in", "Sign In", "登录", "Log in", "Login"):
                try:
                    page.get_by_role("link", name=name).first.click(timeout=3000)
                    signin_clicked = True
                    break
                except Exception:
                    try:
                        page.get_by_role("button", name=name).first.click(timeout=3000)
                        signin_clicked = True
                        break
                    except Exception:
                        continue
            if not signin_clicked:
                raise RuntimeError('Could not find "Sign in" (or similar) on the page. Check the button/link text.')
            # Wait for redirect to login page and for the login form to appear
            page.wait_for_selector("input[type='password']", state="visible", timeout=3000)

            # --- Fill username: try common labels/placeholders, then fallback to first text/email input ---
            username_filled = False
            for label in ("Email", "Username", "邮箱", "手机号", "Email address"):
                try:
                    page.get_by_label(label).first.fill(USERNAME, timeout=3000)
                    username_filled = True
                    break
                except Exception:
                    continue
            if not username_filled:
                try:
                    page.locator("input[type='email']").first.fill(USERNAME, timeout=3000)
                    username_filled = True
                except Exception:
                    page.locator("input[type='text']").first.fill(USERNAME, timeout=3000)
                    username_filled = True
            if not username_filled:
                raise RuntimeError("Could not find username/email field. Check the page or add the right selector.")

            # --- Fill password: label or type=password ---
            try:
                page.get_by_label("Password").first.fill(PASSWORD, timeout=3000)
            except Exception:
                page.locator("input[type='password']").first.fill(PASSWORD, timeout=3000)

            # --- Click login ---
            for btn_name in ("Log in", "Login", "登录", "Sign in"):
                try:
                    page.get_by_role("button", name=btn_name).first.click(timeout=2000)
                    break
                except Exception:
                    continue
            else:
                page.locator("button[type='submit'], input[type='submit']").first.click(timeout=3000)


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