"""Persist queue data to JSON so it survives app restarts."""
import json
import os
from datetime import datetime

from app.models.video_metadata import VideoMetadata
from app.utils.config import PROJECT_ROOT

DATA_FILE = os.path.join(PROJECT_ROOT, "queue_data.json")


def save_queue(queue: list[VideoMetadata]):
    """Save the video queue to disk."""
    data = []
    for m in queue:
        entry = {
            "url": m.url,
            "video_id": m.video_id,
            "title": m.title,
            "description": m.description,
            "duration": m.duration,
            "duration_str": m.duration_str,
            "thumbnail_url": m.thumbnail_url,
            "tags": m.tags,
            "uploader": m.uploader,
            "upload_date": m.upload_date,
            "local_file_path": m.local_file_path,
            "thumbnail_local_path": m.thumbnail_local_path,
            "scheduled_date": m.scheduled_date.isoformat() if m.scheduled_date else None,
            "status": m.status,
        }
        data.append(entry)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[DataStore] Saved {len(data)} videos to {DATA_FILE}")


def load_queue() -> list[VideoMetadata]:
    """Load the video queue from disk. Returns empty list if no saved data."""
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    queue = []
    for entry in data:
        m = VideoMetadata(
            url=entry.get("url", ""),
            video_id=entry.get("video_id", ""),
            title=entry.get("title", ""),
            description=entry.get("description", ""),
            duration=entry.get("duration", 0),
            duration_str=entry.get("duration_str", "00:00"),
            thumbnail_url=entry.get("thumbnail_url", ""),
            tags=entry.get("tags", []),
            uploader=entry.get("uploader", ""),
            upload_date=entry.get("upload_date", ""),
            local_file_path=entry.get("local_file_path"),
            thumbnail_local_path=entry.get("thumbnail_local_path"),
            status=entry.get("status", "ready"),
        )

        sched = entry.get("scheduled_date")
        if sched:
            try:
                m.scheduled_date = datetime.fromisoformat(sched)
            except (ValueError, TypeError):
                m.scheduled_date = None

        # Fix statuses: if was downloading/uploading/fetching, reset to appropriate state
        if m.status in ("fetching", "pending"):
            m.status = "ready" if m.video_id else "pending"
        elif m.status == "downloading":
            # Check if file exists (might have finished)
            if m.local_file_path and os.path.exists(m.local_file_path):
                m.status = "downloaded"
            else:
                m.status = "ready"
        elif m.status == "uploading":
            m.status = "downloaded" if (m.local_file_path and os.path.exists(m.local_file_path)) else "ready"

        queue.append(m)

    print(f"[DataStore] Loaded {len(queue)} videos from {DATA_FILE}")
    return queue
