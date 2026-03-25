import os
import glob

from app.utils.config import DOWNLOAD_DIR


def ensure_download_dir():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def cleanup_file(path: str):
    """Delete a specific file if it exists."""
    if path and os.path.exists(path):
        os.remove(path)


def cleanup_all():
    """Remove all files in the downloads directory."""
    if os.path.exists(DOWNLOAD_DIR):
        for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
            try:
                os.remove(f)
            except OSError:
                pass
