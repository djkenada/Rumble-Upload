"""Extract YouTube cookies from the Chrome debugging session and save as Netscape cookie file."""
import os
import time
from selenium.webdriver.common.by import By
from app.utils.config import DOWNLOAD_DIR


COOKIE_FILE = os.path.join(DOWNLOAD_DIR, "cookies.txt")


def export_cookies_from_selenium(driver) -> str:
    """Navigate to YouTube in the Selenium-connected Chrome, grab cookies, save to file.

    The user must already be logged into YouTube in this Chrome session.
    Returns the path to the cookies file.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Navigate to YouTube to get cookies
    driver.get("https://www.youtube.com")
    time.sleep(5)

    # Check if logged in by looking for avatar/sign-in button
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        if "Sign in" in page_text[:500]:
            print("[Cookies] WARNING: Not logged into YouTube! Cookies may not work.")
            print("[Cookies] Please log into YouTube in this browser first.")
    except Exception:
        pass

    # Get YouTube cookies
    yt_cookies = driver.get_cookies()
    yt_count = len(yt_cookies)
    print(f"[Cookies] Got {yt_count} cookies from youtube.com")

    # Also visit google.com to get auth cookies
    driver.get("https://accounts.google.com")
    time.sleep(3)
    google_cookies = driver.get_cookies()
    print(f"[Cookies] Got {len(google_cookies)} cookies from google.com")

    # Merge all cookies (YouTube + Google auth)
    all_cookies = {}
    for c in yt_cookies + google_cookies:
        key = (c.get("domain", ""), c.get("name", ""))
        all_cookies[key] = c

    # Write Netscape cookie format
    with open(COOKIE_FILE, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# This file was generated automatically\n\n")
        for c in all_cookies.values():
            domain = c.get("domain", "")
            flag = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path", "/")
            secure = "TRUE" if c.get("secure", False) else "FALSE"
            expiry = str(int(c.get("expiry", 0))) if c.get("expiry") else "0"
            name = c.get("name", "")
            value = c.get("value", "")
            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")

    total = len(all_cookies)
    print(f"[Cookies] Exported {total} cookies to {COOKIE_FILE}")

    # Navigate back to Rumble
    driver.get("https://rumble.com/upload.php")

    return COOKIE_FILE


def cookie_file_exists() -> bool:
    return os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 100
