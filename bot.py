import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

load_dotenv()

LOGIN_URL = os.getenv("LOGIN_URL", "https://example.com/login")
USERNAME = os.getenv("BOT_USERNAME")
PASSWORD = os.getenv("BOT_PASSWORD")

def main():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Set BOT_USERNAME and BOT_PASSWORD env vars before running.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # set True later
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            # --- Fill login form ---
            # Prefer robust locators. Update these to match the site.
            page.get_by_label("Email").fill(USERNAME)       # or "Username"
            page.get_by_label("Password").fill(PASSWORD)

            # --- Click login ---
            page.get_by_role("button", name="Log in").click()

            # --- Confirm login succeeded ---
            # Change this to something that exists only after login.
            page.wait_for_url("**/dashboard**", timeout=15000)

            # --- Example: click something after login ---
            page.get_by_role("link", name="Profile").click()

            print("✅ Logged in and clicked Profile")

        except PWTimeout:
            page.screenshot(path="error.png", full_page=True)
            print("❌ Timed out. Saved screenshot to error.png")
            raise
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    main()