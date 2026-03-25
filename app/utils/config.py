import os
import sys


def _get_project_root():
    """Get the project root - works both in dev and when frozen as exe."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe - use the exe's directory
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


PROJECT_ROOT = _get_project_root()
DOWNLOAD_DIR = os.path.join(PROJECT_ROOT, "downloads")
CHROME_DEBUG_PORT = 9222
CHROME_PROFILE_DIR = os.path.join(os.path.expanduser("~"), "RumbleUploader_ChromeProfile")
RUMBLE_UPLOAD_URL = "https://rumble.com/upload.php"
