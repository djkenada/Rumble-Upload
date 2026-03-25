import os
import shutil
import subprocess
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from app.models.video_metadata import VideoMetadata
from app.utils.config import CHROME_DEBUG_PORT, CHROME_PROFILE_DIR, RUMBLE_UPLOAD_URL

ACTION_DELAY = 2


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
        "https://rumble.com",
    ])
    return proc


def connect() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{CHROME_DEBUG_PORT}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def check_login_status(driver: webdriver.Chrome) -> bool:
    driver.get(RUMBLE_UPLOAD_URL)
    time.sleep(5)
    current_url = driver.current_url.lower()
    if "login" in current_url or "auth" in current_url or "sign" in current_url:
        return False
    try:
        driver.find_element(By.ID, "Filedata")
        return True
    except Exception:
        return False


def _set_value_js(driver, element, text):
    driver.execute_script("""
        var el = arguments[0];
        var text = arguments[1];
        el.focus();
        el.value = text;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    """, element, text)


def upload_video(driver: webdriver.Chrome, metadata: VideoMetadata, progress_callback=None) -> bool:
    """Upload a video to Rumble using Selenium automation.

    Rumble upload is a two-step form:
      Form 1: file, title, description, thumbnail, tags, categories, visibility/schedule
      Form 2: copyright/terms checkboxes, final submit
    """
    if not metadata.local_file_path or not os.path.exists(metadata.local_file_path):
        raise FileNotFoundError(f"Video file not found: {metadata.local_file_path}")

    print(f"[Rumble] Starting upload for: {metadata.title}")
    print(f"[Rumble] File: {metadata.local_file_path}")

    if progress_callback:
        progress_callback(0.0, "Navigating to Rumble upload page...")

    driver.get(RUMBLE_UPLOAD_URL)
    time.sleep(3)

    wait = WebDriverWait(driver, 30)

    # ---- STEP 1: Upload the video file ----
    file_input = wait.until(EC.presence_of_element_located((By.ID, "Filedata")))
    time.sleep(ACTION_DELAY)

    if progress_callback:
        progress_callback(0.05, "Sending video file...")

    file_input.send_keys(metadata.local_file_path)
    print(f"[Rumble] File sent to upload input")

    if progress_callback:
        progress_callback(0.1, "Waiting for file to upload to Rumble...")

    # Wait for the title field to become visible (means file upload is processing)
    title_field = None
    start_time = time.time()
    while time.time() - start_time < 1800:
        try:
            el = driver.find_element(By.ID, "title")
            if el.is_displayed():
                title_field = el
                break
        except Exception:
            pass
        time.sleep(5)
        elapsed = time.time() - start_time
        if progress_callback:
            est = min(0.1 + (elapsed / 600) * 0.4, 0.5)
            progress_callback(est, f"Uploading to Rumble... ({int(elapsed)}s)")

    if not title_field:
        raise TimeoutError("Title field did not appear. Upload may have failed.")

    print(f"[Rumble] Upload form appeared after {int(time.time() - start_time)}s")
    time.sleep(ACTION_DELAY)

    # ---- STEP 2: Fill title ----
    if progress_callback:
        progress_callback(0.55, "Filling title...")

    title_field.click()
    time.sleep(0.5)
    title_field.send_keys(Keys.CONTROL, "a")
    time.sleep(0.3)
    title_field.send_keys(metadata.title[:255])
    time.sleep(ACTION_DELAY)
    print(f"[Rumble] Title: {metadata.title[:60]}")

    # ---- STEP 3: Fill description ----
    if progress_callback:
        progress_callback(0.6, "Filling description...")

    desc_text = metadata.description[:5000] if metadata.description else ""
    if desc_text:
        try:
            desc_field = driver.find_element(By.ID, "description")
            if desc_field.is_displayed():
                desc_field.click()
                time.sleep(0.5)
                # Use JS to set value (faster and more reliable for large text)
                _set_value_js(driver, desc_field, desc_text)
                time.sleep(0.5)
                # Verify
                current_val = desc_field.get_attribute("value") or ""
                if len(current_val) < 10 and len(desc_text) > 10:
                    # JS failed, use send_keys
                    desc_field.send_keys(Keys.CONTROL, "a")
                    time.sleep(0.3)
                    desc_field.send_keys(desc_text[:2000])  # Limit for send_keys
                time.sleep(ACTION_DELAY)
                print(f"[Rumble] Description filled ({len(desc_text)} chars)")
            else:
                print(f"[Rumble] Description field not displayed")
        except Exception as e:
            print(f"[Rumble] Description error: {e}")

    # ---- STEP 4: Upload thumbnail ----
    if progress_callback:
        progress_callback(0.65, "Uploading thumbnail...")

    if metadata.thumbnail_local_path and os.path.exists(metadata.thumbnail_local_path):
        try:
            # Find the actual file input for thumbnail (may be hidden)
            # First try to find an input[type=file] related to thumbnails
            thumb_path = os.path.abspath(metadata.thumbnail_local_path)
            thumb_uploaded = False

            # Try direct file input by ID
            try:
                thumb_input = driver.find_element(By.ID, "customThumb")
                tag = thumb_input.tag_name.lower()
                input_type = thumb_input.get_attribute("type") or ""
                if tag == "input" and input_type.lower() == "file":
                    thumb_input.send_keys(thumb_path)
                    thumb_uploaded = True
                    print(f"[Rumble] Thumbnail uploaded via #customThumb input")
                else:
                    print(f"[Rumble] #customThumb is {tag}[{input_type}], not file input")
            except Exception:
                pass

            # If that didn't work, find any hidden file input near thumbnail area
            if not thumb_uploaded:
                try:
                    file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    for fi in file_inputs:
                        name = fi.get_attribute("name") or ""
                        fid = fi.get_attribute("id") or ""
                        accept = fi.get_attribute("accept") or ""
                        if any(kw in (name + fid + accept).lower() for kw in ["thumb", "image", "photo", "custom"]):
                            # Make visible if hidden
                            driver.execute_script("arguments[0].style.display='block'; arguments[0].style.visibility='visible';", fi)
                            fi.send_keys(thumb_path)
                            thumb_uploaded = True
                            print(f"[Rumble] Thumbnail uploaded via file input: {name or fid}")
                            break
                except Exception as e2:
                    print(f"[Rumble] Hidden file input search error: {e2}")

            if not thumb_uploaded:
                print(f"[Rumble] Skipping thumbnail - no suitable file input found")

            time.sleep(ACTION_DELAY)
        except Exception as e:
            print(f"[Rumble] Thumbnail error: {e}")

    # ---- STEP 5: Fill tags ----
    if progress_callback:
        progress_callback(0.7, "Filling tags...")

    tags_str = ", ".join(metadata.tags[:10]) if metadata.tags else ""
    if tags_str:
        try:
            tags_field = driver.find_element(By.ID, "tags")
            if tags_field.is_displayed():
                tags_field.click()
                time.sleep(0.5)
                tags_field.send_keys(Keys.CONTROL, "a")
                time.sleep(0.3)
                tags_field.send_keys(tags_str)
                time.sleep(ACTION_DELAY)
                print(f"[Rumble] Tags: {tags_str[:60]}")
        except Exception as e:
            print(f"[Rumble] Tags error: {e}")

    # ---- STEP 6: Select category (News) ----
    if progress_callback:
        progress_callback(0.77, "Setting category...")

    time.sleep(ACTION_DELAY)
    try:
        # Click the category input to open the dropdown
        cat_input = driver.find_element(By.CSS_SELECTOR, "input[name='primary-category']")
        cat_input.click()
        time.sleep(1)

        # Find and click the "News" option
        news_option = driver.find_element(By.CSS_SELECTOR, "div.select-option[data-label='News']")
        news_option.click()
        time.sleep(1)

        # Verify the hidden value was set
        hidden_val = driver.find_element(By.ID, "category_primary").get_attribute("value")
        print(f"[Rumble] Category set to News (value={hidden_val})")
    except Exception as e:
        print(f"[Rumble] Category error: {e}")
        # Fallback: try setting via JS
        try:
            driver.execute_script("""
                var opt = document.querySelector('div.select-option[data-label="News"]');
                if (opt) { opt.click(); }
            """)
            time.sleep(1)
            print(f"[Rumble] Category set via JS fallback")
        except Exception:
            pass

    # ---- STEP 7: Set visibility / schedule ----
    if progress_callback:
        progress_callback(0.75, "Setting visibility/schedule...")

    time.sleep(ACTION_DELAY)

    # Scroll to the bottom of the page so schedule/visibility fields are visible
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1.5)
    print("[Rumble] Scrolled to bottom of page")

    if metadata.scheduled_date:
        # Click the "scheduler" radio button to enable scheduling
        try:
            scheduler_radio = driver.find_element(By.ID, "scheduler")
            # Scroll the radio into view first
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", scheduler_radio)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", scheduler_radio)
            time.sleep(ACTION_DELAY)

            # Set the date via the daterangepicker jQuery API
            # Rumble daterangepicker format: "3/25/2026 - 08:00 am"
            d = metadata.scheduled_date
            schedule_str = f"{d.month}/{d.day}/{d.year} - {d.strftime('%I:%M %p').lower()}"
            driver.execute_script("""
                var dp = $('#scheduler_datetime').data('daterangepicker');
                if (dp) {
                    var m = moment(arguments[0]);
                    dp.setStartDate(m);
                    dp.setEndDate(m);
                }
                // Also set the input value directly as backup
                document.getElementById('scheduler_datetime').value = arguments[0];
            """, schedule_str)
            time.sleep(ACTION_DELAY)

            # Click the Apply button on the date picker if visible
            try:
                apply_btn = driver.find_element(By.CSS_SELECTOR, ".daterangepicker .applyBtn")
                if apply_btn.is_displayed():
                    apply_btn.click()
                    time.sleep(1)
            except Exception:
                pass

            # Click elsewhere to close the picker
            driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(1)

            print(f"[Rumble] Scheduled: {schedule_str}")
        except Exception as e:
            print(f"[Rumble] Schedule error: {e}")
            # Fall back to public
            try:
                public_radio = driver.find_element(By.ID, "visibility_public")
                driver.execute_script("arguments[0].click();", public_radio)
                time.sleep(ACTION_DELAY)
            except Exception:
                pass
    else:
        # Set to public
        try:
            public_radio = driver.find_element(By.ID, "visibility_public")
            driver.execute_script("arguments[0].click();", public_radio)
            time.sleep(ACTION_DELAY)
            print(f"[Rumble] Visibility: public")
        except Exception as e:
            print(f"[Rumble] Visibility error: {e}")

    # ---- STEP 8: Click "Upload" button (first form submit) ----
    if progress_callback:
        progress_callback(0.8, "Submitting form 1...")

    time.sleep(ACTION_DELAY)
    try:
        submit1 = driver.find_element(By.ID, "submitForm")
        driver.execute_script("arguments[0].scrollIntoView(true);", submit1)
        time.sleep(1)
        submit1.click()
        print(f"[Rumble] Form 1 submitted (Upload button clicked)")
    except Exception as e:
        raise RuntimeError(f"Could not click Upload button: {e}")

    # ---- STEP 9: Wait for form 2 (copyright/terms) ----
    if progress_callback:
        progress_callback(0.85, "Waiting for terms page...")

    time.sleep(5)

    # Wait for the copyright/terms checkboxes to appear
    try:
        crights = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "crights"))
        )
        time.sleep(ACTION_DELAY)

        # Check copyright checkbox
        if not crights.is_selected():
            driver.execute_script("arguments[0].click();", crights)
            time.sleep(1)
        print(f"[Rumble] Copyright checkbox checked")

        # Check terms checkbox
        cterms = driver.find_element(By.ID, "cterms")
        if not cterms.is_selected():
            driver.execute_script("arguments[0].click();", cterms)
            time.sleep(1)
        print(f"[Rumble] Terms checkbox checked")
    except Exception as e:
        print(f"[Rumble] Terms page error: {e}")
        # Try to find any visible checkboxes
        try:
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            for cb in checkboxes:
                if cb.is_displayed() and not cb.is_selected():
                    driver.execute_script("arguments[0].click();", cb)
                    time.sleep(1)
        except Exception:
            pass

    if progress_callback:
        progress_callback(0.9, "Final submit...")

    # ---- STEP 10: Click final "Submit" button (form 2) ----
    time.sleep(ACTION_DELAY)
    try:
        submit2 = driver.find_element(By.ID, "submitForm2")
        # Wait for it to become visible/clickable
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "submitForm2"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", submit2)
        time.sleep(1)
        submit2.click()
        print(f"[Rumble] Form 2 submitted (final Submit clicked)")
    except Exception as e:
        print(f"[Rumble] Form 2 submit error: {e}")
        # Try alternative
        try:
            submit2 = driver.find_element(By.ID, "submitForm2")
            driver.execute_script("arguments[0].click();", submit2)
            print(f"[Rumble] Form 2 submitted via JS click")
        except Exception as e2:
            raise RuntimeError(f"Could not click final Submit: {e2}")

    # Wait for confirmation
    time.sleep(10)

    if progress_callback:
        progress_callback(1.0, "Upload submitted!")

    print(f"[Rumble] Upload complete for: {metadata.title}")
    return True
