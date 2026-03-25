import json
import os
import subprocess
import sys
import requests

# Hide console windows for subprocesses on Windows
_STARTUPINFO = None
if sys.platform == "win32":
    _STARTUPINFO = subprocess.STARTUPINFO()
    _STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUPINFO.wShowWindow = 0  # SW_HIDE

# Ensure bundled tools (deno, ffmpeg) are in PATH for subprocesses
def _get_env():
    """Get environment with app directory in PATH so yt-dlp can find deno/ffmpeg."""
    env = os.environ.copy()
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env["PATH"] = app_dir + os.pathsep + env.get("PATH", "")
    return env

from app.models.video_metadata import VideoMetadata
from app.services.title_rewriter import rewrite_title
from app.utils.config import DOWNLOAD_DIR


def _safe_str(value) -> str:
    if value is None:
        return ""
    return str(value)


def _get_ytdlp_cmd() -> list[str]:
    """Get the yt-dlp command as a list of args."""
    # 1. When frozen, use bundled yt_dlp module via the exe itself
    if getattr(sys, 'frozen', False):
        # yt-dlp is bundled as a module - we can't call it directly
        # but the yt-dlp.exe next to our exe should work if Python is installed
        exe_dir = os.path.dirname(sys.executable)
        local_ytdlp = os.path.join(exe_dir, "yt-dlp.exe")
        if os.path.exists(local_ytdlp):
            return [local_ytdlp]
        # Try PATH
        return ["yt-dlp"]

    # 2. Check Python Scripts dir
    python_dir = os.path.dirname(sys.executable)
    scripts_dir = os.path.join(python_dir, "Scripts")
    ytdlp = os.path.join(scripts_dir, "yt-dlp.exe")
    if os.path.exists(ytdlp):
        return [ytdlp]

    # 3. Fallback to PATH
    return ["yt-dlp"]


def _get_cookie_args() -> list[str]:
    """Get cookie arguments if cookie file exists."""
    cookies_file = os.path.join(DOWNLOAD_DIR, "cookies.txt")
    if os.path.exists(cookies_file):
        return ["--cookies", cookies_file]
    return []


def _get_base_args() -> list[str]:
    """Base yt-dlp CLI arguments."""
    return _get_ytdlp_cmd() + [
        "--remote-components", "ejs:github",
        "--extractor-args", "youtube:player_client=web,mweb,android",
    ] + _get_cookie_args()


def fetch_info(url: str) -> VideoMetadata:
    """Fetch video metadata from YouTube without downloading."""
    cmd = _get_base_args() + [
        "--skip-download",
        "--dump-json",
        "--ignore-no-formats-error",
        url,
    ]

    print(f"[fetch_info] Running: {' '.join(cmd[:6])}...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, startupinfo=_STARTUPINFO, env=_get_env())

    if result.returncode != 0:
        error = result.stderr.strip().split("\n")[-1] if result.stderr else "Unknown error"
        raise RuntimeError(error)

    info = json.loads(result.stdout)

    title = _safe_str(info.get("title"))
    description = _safe_str(info.get("description"))

    duration = info.get("duration", 0) or 0
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        duration_str = f"{minutes}:{seconds:02d}"

    thumbnail_url = _safe_str(info.get("thumbnail"))
    thumbnail_local = None
    if thumbnail_url:
        try:
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            thumbnail_local = os.path.join(DOWNLOAD_DIR, f"{info['id']}_thumb.jpg")
            resp = requests.get(thumbnail_url, timeout=10)
            resp.raise_for_status()
            with open(thumbnail_local, "wb") as f:
                f.write(resp.content)
        except Exception:
            thumbnail_local = None

    raw_tags = info.get("tags") or []
    tags = [_safe_str(t) for t in raw_tags]

    rumble_title = rewrite_title(title)

    return VideoMetadata(
        url=url,
        video_id=_safe_str(info.get("id")),
        title=rumble_title,
        description=description,
        duration=duration,
        duration_str=duration_str,
        thumbnail_url=thumbnail_url,
        tags=tags,
        uploader=_safe_str(info.get("uploader")),
        upload_date=_safe_str(info.get("upload_date")),
        thumbnail_local_path=thumbnail_local,
    )


def download_video(metadata: VideoMetadata, progress_callback=None) -> str:
    """Download the video as mp4 at up to 1080p. Returns the local file path."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    output_path = os.path.join(DOWNLOAD_DIR, f"{metadata.video_id}.%(ext)s")
    expected_mp4 = os.path.join(DOWNLOAD_DIR, f"{metadata.video_id}.mp4")

    cmd = _get_base_args() + [
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "-o", output_path,
        "--newline",
        "--no-overwrites",
        metadata.url,
    ]

    print(f"[download_video] Running: {' '.join(cmd[:8])}...")
    last_error = ""

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=_STARTUPINFO,
        env=_get_env(),
    )

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue

        # Parse progress from yt-dlp output like "[download]  45.2% of 100.00MiB at 5.00MiB/s ETA 00:10"
        if "[download]" in line and "%" in line:
            try:
                pct_str = line.split("%")[0].split()[-1]
                pct = float(pct_str) / 100.0

                # Extract speed and ETA
                parts = line.split()
                speed = ""
                eta = ""
                for i, p in enumerate(parts):
                    if p == "at" and i + 1 < len(parts):
                        speed = parts[i + 1]
                    if p == "ETA" and i + 1 < len(parts):
                        eta = parts[i + 1]

                status = f"Downloading: {pct:.0%}"
                if speed:
                    status += f" | {speed}"
                if eta:
                    status += f" | ETA: {eta}"

                if progress_callback:
                    progress_callback(min(pct, 0.99), status)
            except (ValueError, IndexError):
                pass

        elif "[download] 100%" in line:
            if progress_callback:
                progress_callback(0.99, "Download complete, merging...")

        elif "[Merger]" in line:
            if progress_callback:
                progress_callback(0.99, "Merging audio/video...")

        # Print for debugging
        if "[download]" not in line or "100%" in line or "Destination" in line:
            print(f"[download_video] {line}")

        # Capture error lines
        if "ERROR" in line or "error" in line.lower():
            last_error = line

    proc.wait()

    if proc.returncode != 0:
        err_msg = last_error if last_error else f"yt-dlp exited with code {proc.returncode}"
        raise RuntimeError(err_msg)

    if progress_callback:
        progress_callback(1.0, "Download complete!")

    # Find the output file
    if os.path.exists(expected_mp4):
        metadata.local_file_path = expected_mp4
        print(f"[download_video] Output: {expected_mp4} ({os.path.getsize(expected_mp4)} bytes)")
        return expected_mp4

    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(metadata.video_id) and not f.endswith("_thumb.jpg"):
            path = os.path.join(DOWNLOAD_DIR, f)
            metadata.local_file_path = path
            print(f"[download_video] Fallback output: {path}")
            return path

    raise FileNotFoundError(f"Downloaded file not found for {metadata.video_id}")
