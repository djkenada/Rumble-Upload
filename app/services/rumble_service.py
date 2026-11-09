"""Upload videos through Rumble Studio (https://studio.rumble.com) by driving Chrome.

Studio's upload is a modal on the dashboard with two steps:
  Step 1 "Details":    title, description, author, category, thumbnail, tags
  Step 2 "Visibility": monetization, visibility/schedule, alerts, terms checkboxes
The video file transfers in the background while step 1 is filled in. "Next" stays
disabled until the transfer is done, and the footer shows the upload percentage.
"""
import datetime
import os
import re
import shutil
import subprocess
import time

from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

from app.models.video_metadata import VideoMetadata
from app.utils.config import (
    CHROME_DEBUG_PORT,
    CHROME_PROFILE_DIR,
    DEFAULT_CATEGORY,
    RUMBLE_STUDIO_URL,
)

ACTION_DELAY = 1

TITLE_MAX = 100          # Studio's limits (the old upload page allowed 255)
DESCRIPTION_MAX = 5000
SCHEDULE_STEP_MINUTES = 5  # Studio's time list goes in 5-minute steps

UPLOAD_STALL_TIMEOUT = 15 * 60      # give up if the percentage hasn't moved for this long
UPLOAD_MAX_TIME = 12 * 60 * 60      # absolute cap for one file

DIALOG = "[role=dialog]"


def _find_chrome_exe() -> str:
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    chrome_in_path = shutil.which("chrome") or shutil.which("chrome.exe")
    if chrome_in_path:
        return chrome_in_path
    raise FileNotFoundError("Chrome not found. Please install Google Chrome.")


def launch_chrome() -> subprocess.Popen:
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    chrome_exe = _find_chrome_exe()
    proc = subprocess.Popen([
        chrome_exe,
        f"--remote-debugging-port={CHROME_DEBUG_PORT}",
        f"--user-data-dir={CHROME_PROFILE_DIR}",
        RUMBLE_STUDIO_URL,
    ])
    return proc


def connect() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{CHROME_DEBUG_PORT}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


# ---------------------------------------------------------------- helpers

def _visible(elements):
    return [e for e in elements if e.is_displayed()]


def _find_upload_button(driver, timeout=20):
    """The dashboard's "Upload video" button; only present when signed in to Studio."""
    end = time.time() + timeout
    while time.time() < end:
        buttons = _visible(driver.find_elements(By.XPATH, "//button[normalize-space()='Upload video']"))
        if buttons:
            return buttons[0]
        time.sleep(0.5)
    return None


def check_login_status(driver: webdriver.Chrome) -> bool:
    driver.get(RUMBLE_STUDIO_URL)
    return _find_upload_button(driver) is not None


def _click(driver, element, label="element"):
    """Scroll an element to the middle of its scroll area and click it, with a JS click as fallback."""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.4)
    try:
        element.click()
    except ElementClickInterceptedException as e:
        print(f"[Rumble] {label}: normal click blocked, clicking via JS ({str(e).splitlines()[0][:120]})")
        driver.execute_script("arguments[0].click();", element)


def _set_text(driver, element, text):
    """Set the value of a React-controlled input/textarea so that React sees the change."""
    driver.execute_script("""
        var el = arguments[0], text = arguments[1];
        var proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype
                                              : window.HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, text);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
    """, element, text)
    time.sleep(0.3)
    if (element.get_attribute("value") or "") != text:
        # Fall back to typing
        element.click()
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(Keys.DELETE)
        element.send_keys(text)


def _dialog(driver):
    dialogs = driver.find_elements(By.CSS_SELECTOR, DIALOG)
    if not dialogs:
        raise RuntimeError("Rumble Studio's upload window closed unexpectedly.")
    return dialogs[0]


_FOOTER_STATE_JS = """
    var d = document.querySelector('[role=dialog]');
    if (!d) return {open: false};
    var err = d.querySelector('[data-sentry-component="CIVideoUploadFooterErrorMessage"]');
    var done = d.querySelector('[role=status][aria-live]');
    var busy = d.querySelector('[data-sentry-component="CIVideoUploadFooterUploadStatus"]');
    function txt(e) { return e ? (e.innerText || '').replace(/\\s+/g, ' ').trim() : ''; }
    return {open: true, error: txt(err), done: txt(done), busy: txt(busy)};
"""


def _footer_state(driver) -> dict:
    return driver.execute_script(_FOOTER_STATE_JS) or {"open": False}


def _raise_on_footer_error(driver):
    state = _footer_state(driver)
    if state.get("error"):
        raise RuntimeError(f"Rumble reported: {state['error']}")
    return state


def _wait_for_file_upload(driver, progress_callback=None, poll_interval=2):
    """Block until Studio reports the video file has finished uploading and passed its checks.

    While uploading, the footer reads "Uploading 43% · 12 MB/s ... 2m left"; when
    finished it becomes "Checks complete. No issues found.". Raises if Studio shows
    an error or the percentage stops moving.
    """
    start = time.time()
    last_change = start
    last_seen = None

    while True:
        state = _footer_state(driver)
        if not state.get("open"):
            raise RuntimeError("Rumble Studio's upload window closed before the upload finished.")
        if state.get("error"):
            raise RuntimeError(f"Rumble reported a file upload error: {state['error']}")
        if "complete" in state.get("done", "").lower():
            print(f"[Rumble] File upload finished after {int(time.time() - start)}s")
            return

        busy = state.get("busy", "")
        match = re.search(r"(\d+)\s*%", busy)
        percent = int(match.group(1)) if match else None

        now = time.time()
        if percent != last_seen:
            last_seen = percent
            last_change = now
        if now - last_change > UPLOAD_STALL_TIMEOUT:
            where = f"{percent}%" if percent is not None else "an unknown point"
            raise TimeoutError(f"File upload stalled at {where} for {UPLOAD_STALL_TIMEOUT // 60} minutes.")
        if now - start > UPLOAD_MAX_TIME:
            raise TimeoutError("File upload did not finish in time.")

        if progress_callback:
            shown = percent if percent is not None else 0
            progress_callback(0.1 + 0.7 * shown / 100, (busy or "Preparing upload...")[:40])
        time.sleep(poll_interval)


def _select_category(driver, dialog, category: str):
    """Pick the primary category. Studio pre-fills the one used last time, so always set it."""
    dropdowns = dialog.find_elements(By.XPATH, ".//button[img[@alt='Down arrow']]")
    if not dropdowns:
        raise RuntimeError("Category selector not found.")
    primary = dropdowns[0]
    if primary.text.strip() == category:
        return
    _click(driver, primary, "Category")
    time.sleep(0.8)
    search = _visible(driver.find_elements(By.CSS_SELECTOR, "input[placeholder='Search']"))
    if search:
        search[0].send_keys(category)
        time.sleep(0.8)
    options = _visible(driver.find_elements(
        By.XPATH, f"//span[normalize-space()=\"{category}\" and not(ancestor::button)]"))
    if not options:
        # Close the list again and report
        primary.click()
        raise RuntimeError(f"Rumble has no category called '{category}'.")
    options[0].click()
    time.sleep(0.6)
    chosen = dialog.find_elements(By.XPATH, ".//button[img[@alt='Down arrow']]")[0].text.strip()
    if chosen != category:
        raise RuntimeError(f"Category did not change to '{category}' (shows '{chosen}').")


def round_schedule(dt):
    """Round a datetime to Studio's 5-minute grid."""
    step = SCHEDULE_STEP_MINUTES
    total = dt.hour * 60 + dt.minute + (1 if dt.second >= 30 else 0)
    rounded = int(round(total / step) * step)
    base = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return base + datetime.timedelta(minutes=rounded)


def _set_schedule(driver, dialog, when):
    """Choose "Scheduled" and pick the date and time in Studio's date picker."""
    when = round_schedule(when)
    radio = dialog.find_element(By.CSS_SELECTOR, "button[role=radio][value='scheduled']")
    _click(driver, radio, "Scheduled")
    time.sleep(1)
    field = dialog.find_element(By.CSS_SELECTOR, "input[placeholder='Pick a time']")

    def open_picker():
        if not driver.find_elements(By.CSS_SELECTOR, ".react-datepicker"):
            _click(driver, field, "Schedule date")
            time.sleep(0.8)

    open_picker()
    target_month = when.strftime("%B %Y")
    for _ in range(36):
        current = driver.find_element(By.CSS_SELECTOR, ".react-datepicker__current-month").text.strip()
        if current == target_month:
            break
        cur_dt = datetime.datetime.strptime(current, "%B %Y")
        forward = (when.year, when.month) > (cur_dt.year, cur_dt.month)
        nav = driver.find_elements(
            By.CSS_SELECTOR,
            ".react-datepicker__navigation--next" if forward else ".react-datepicker__navigation--previous")
        if not nav:
            raise RuntimeError(f"Rumble won't schedule in {target_month}; that month isn't selectable.")
        nav[0].click()
        time.sleep(0.3)
    else:
        raise RuntimeError(f"Could not reach {target_month} in Rumble's date picker.")

    day = driver.find_element(
        By.CSS_SELECTOR,
        f".react-datepicker__day--{when.day:03d}:not(.react-datepicker__day--outside-month)")
    if day.get_attribute("aria-disabled") == "true":
        raise RuntimeError(f"Rumble won't schedule on {when.strftime('%m/%d/%Y')}; the date is in the past.")
    day.click()
    time.sleep(0.6)

    open_picker()
    hour12 = when.hour % 12 or 12
    label = f"{hour12}:{when.minute:02d} {'AM' if when.hour < 12 else 'PM'}"
    slot = driver.find_element(
        By.XPATH, f"//li[contains(@class,'react-datepicker__time-list-item') and normalize-space()='{label}']")
    if "disabled" in (slot.get_attribute("class") or ""):
        raise RuntimeError(f"Rumble won't schedule at {label} on that day; the time is in the past.")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", slot)
    time.sleep(0.2)
    slot.click()
    time.sleep(0.6)

    # The field reads like "Thursday, December 03, 2026 9:30AM"
    shown = field.get_attribute("value") or ""
    expected = f"{when.strftime('%A, %B %d, %Y')} {hour12}:{when.minute:02d}{'AM' if when.hour < 12 else 'PM'}"
    if shown != expected:
        raise RuntimeError(f"Schedule shows '{shown}', expected '{expected}'.")
    print(f"[Rumble] Scheduled: {shown}")


def _footer_button(dialog):
    """The primary footer button: "Next" (go to next step) or "Finish" (finish and close)."""
    for label in ("Finish and close", "Go to next step"):
        found = dialog.find_elements(By.CSS_SELECTOR, f"button[aria-label='{label}']")
        if found:
            return found[0], label
    raise RuntimeError("Next/Finish button not found in Rumble Studio's upload window.")


def _click_footer(driver, expect_label):
    button, label = _footer_button(_dialog(driver))
    if label != expect_label:
        raise RuntimeError(f"Expected the '{expect_label}' button but found '{label}'.")
    end = time.time() + 20
    while button.get_attribute("aria-disabled") == "true" and time.time() < end:
        time.sleep(0.5)
        button, label = _footer_button(_dialog(driver))
    if button.get_attribute("aria-disabled") == "true":
        _raise_on_footer_error(driver)
        raise RuntimeError(f"Rumble keeps '{button.text.strip() or expect_label}' disabled; "
                           "a required field is probably missing.")
    _click(driver, button, expect_label)


# ---------------------------------------------------------------- upload

def upload_video(driver: webdriver.Chrome, metadata: VideoMetadata, progress_callback=None,
                 finish: bool = True) -> bool:
    """Upload one video through Rumble Studio.

    With finish=False everything is filled in but the final "Finish" button is not
    clicked, so nothing is published (used for testing).
    """
    if not metadata.local_file_path or not os.path.exists(metadata.local_file_path):
        raise FileNotFoundError(f"Video file not found: {metadata.local_file_path}")

    def report(pct, status):
        if progress_callback:
            progress_callback(pct, status)

    title = (metadata.title or "").strip()[:TITLE_MAX]
    if not title:
        raise ValueError("A title is required.")
    # Studio requires a description; fall back to the title rather than fail.
    description = (metadata.description or "").strip()[:DESCRIPTION_MAX] or title
    category = metadata.category or DEFAULT_CATEGORY

    print(f"[Rumble] Starting upload for: {title}")
    print(f"[Rumble] File: {metadata.local_file_path}")

    # ---- Open the upload window ----
    report(0.0, "Opening Rumble Studio...")
    driver.get(RUMBLE_STUDIO_URL)
    upload_button = _find_upload_button(driver)
    if not upload_button:
        raise RuntimeError("Not logged into Rumble Studio. Log in in the Chrome window, then try again.")
    time.sleep(ACTION_DELAY)
    _click(driver, upload_button, "Upload video")

    end = time.time() + 20
    file_input = None
    while time.time() < end and file_input is None:
        found = driver.find_elements(By.CSS_SELECTOR, f"{DIALOG} input[type=file][accept^='video']")
        file_input = found[0] if found else None
        time.sleep(0.5)
    if file_input is None:
        raise RuntimeError("Rumble Studio's upload window did not open.")

    # ---- Step 1: choose the file; the transfer starts straight away ----
    report(0.01, "Sending video file...")
    file_input.send_keys(os.path.abspath(metadata.local_file_path))
    print("[Rumble] File sent to upload input")

    report(0.02, "Waiting for the details form...")
    end = time.time() + 120
    title_field = None
    while time.time() < end and title_field is None:
        _raise_on_footer_error(driver)
        found = _visible(driver.find_elements(By.CSS_SELECTOR, f"{DIALOG} input[placeholder^='Title']"))
        title_field = found[0] if found else None
        time.sleep(0.5)
    if title_field is None:
        raise TimeoutError("Rumble Studio did not show the details form after choosing the file.")
    dialog = _dialog(driver)
    time.sleep(ACTION_DELAY)

    report(0.03, "Filling title...")
    _set_text(driver, title_field, title)
    print(f"[Rumble] Title: {title[:60]}")

    report(0.04, "Filling description...")
    desc_field = dialog.find_element(By.CSS_SELECTOR, "textarea[placeholder^='Description']")
    _set_text(driver, desc_field, description)
    print(f"[Rumble] Description filled ({len(description)} chars)")

    report(0.05, "Setting category...")
    _select_category(driver, dialog, category)
    print(f"[Rumble] Category: {category}")

    tags_str = ", ".join(t.strip() for t in (metadata.tags or [])[:10] if t.strip())
    if tags_str:
        report(0.07, "Filling tags...")
        try:
            tags_field = dialog.find_element(By.CSS_SELECTOR, "input[placeholder='Add tags']")
            _set_text(driver, tags_field, tags_str)
            print(f"[Rumble] Tags: {tags_str[:60]}")
        except Exception as e:
            print(f"[Rumble] Tags error: {str(e).splitlines()[0]}")

    # ---- Wait for the file itself; Studio keeps "Next" disabled until then ----
    _wait_for_file_upload(driver, progress_callback)

    # ---- Thumbnail: Studio only accepts it once the video itself has finished uploading ----
    if metadata.thumbnail_local_path and os.path.exists(metadata.thumbnail_local_path):
        report(0.81, "Uploading thumbnail...")
        try:
            thumb_input = dialog.find_element(By.CSS_SELECTOR, "input[type=file][accept^='image']")
            thumb_input.send_keys(os.path.abspath(metadata.thumbnail_local_path))
            end = time.time() + 30
            attached = False
            while time.time() < end and not attached:
                attached = bool(dialog.find_elements(By.CSS_SELECTOR, "img[alt='custom-thumbnail-preview']"))
                time.sleep(0.5)
            print("[Rumble] Thumbnail attached" if attached
                  else "[Rumble] Thumbnail was sent but Studio did not show a preview")
        except Exception as e:
            print(f"[Rumble] Thumbnail error: {str(e).splitlines()[0]}")

    report(0.82, "Opening visibility step...")
    time.sleep(ACTION_DELAY)
    _click_footer(driver, "Go to next step")
    time.sleep(1.5)
    dialog = _dialog(driver)

    # ---- Step 2: visibility / schedule ----
    report(0.86, "Setting visibility...")
    section = dialog.find_element(
        By.XPATH, ".//button[@aria-expanded and starts-with(normalize-space(), 'Visibility')]")
    if section.get_attribute("aria-expanded") == "false":
        _click(driver, section, "Visibility")
        time.sleep(1)
    if metadata.scheduled_date:
        _set_schedule(driver, dialog, metadata.scheduled_date)
    else:
        public = dialog.find_element(By.CSS_SELECTOR, "button[role=radio][value='public']")
        if public.get_attribute("aria-checked") != "true":
            _click(driver, public, "Public")
            time.sleep(0.5)
        print("[Rumble] Visibility: public")

    # Some accounts get an extra "Campaigns" step before the last one
    for _ in range(2):
        _, label = _footer_button(_dialog(driver))
        if label == "Finish and close":
            break
        _click_footer(driver, "Go to next step")
        time.sleep(1.5)

    # ---- Terms ----
    report(0.9, "Accepting terms...")
    dialog = _dialog(driver)
    for box_id in ("ci-rumble-exclusive-agreement", "ci-rumble-terms-agreement"):
        box = dialog.find_element(By.ID, box_id)
        if box.get_attribute("aria-checked") != "true":
            _click(driver, box, box_id)
            time.sleep(0.5)
        if _dialog(driver).find_element(By.ID, box_id).get_attribute("aria-checked") != "true":
            raise RuntimeError("Could not tick Rumble's terms checkboxes.")
    print("[Rumble] Terms checkboxes ticked")

    if not finish:
        button, label = _footer_button(_dialog(driver))
        ready = label == "Finish and close" and button.get_attribute("aria-disabled") != "true"
        print(f"[Rumble] Dry run: stopping before Finish (Finish enabled: {ready})")
        if not ready:
            raise RuntimeError("Finish button is not enabled at the end of the form.")
        report(0.95, "Dry run: ready to finish")
        return True

    # ---- Finish ----
    report(0.95, "Finishing...")
    time.sleep(ACTION_DELAY)
    _click_footer(driver, "Finish and close")
    print("[Rumble] Finish clicked")

    # On success Studio closes the window; on failure it shows an error in the footer
    end = time.time() + 180
    while time.time() < end:
        state = _footer_state(driver)
        if not state.get("open"):
            report(1.0, "Upload finished!")
            print(f"[Rumble] Upload complete for: {title}")
            return True
        if state.get("error"):
            raise RuntimeError(f"Rumble could not finish the upload: {state['error']}")
        time.sleep(1)
    raise TimeoutError("Rumble Studio did not confirm the upload after clicking Finish.")
