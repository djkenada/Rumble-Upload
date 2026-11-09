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
            "local_file_path": m.local_file_path,
            "title": m.title,
            "description": m.description,
            "tags": m.tags,
            "thumbnail_local_path": m.thumbnail_local_path,
            "scheduled_date": m.scheduled_date.isoformat() if m.scheduled_date else None,
            "status": m.status,
            "error_message": m.error_message,
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
    seen = set()
    for entry in data:
        path = entry.get("local_file_path")
        # Entries saved by the old YouTube version that were never downloaded
        # have no file, so there is nothing to upload.
        if not path or path in seen:
            continue
        seen.add(path)

        m = VideoMetadata(
            local_file_path=path,
            title=entry.get("title", ""),
            description=entry.get("description", ""),
            tags=entry.get("tags", []),
            thumbnail_local_path=entry.get("thumbnail_local_path"),
            status=entry.get("status", "ready"),
            error_message=entry.get("error_message", ""),
        )

        sched = entry.get("scheduled_date")
        if sched:
            try:
                m.scheduled_date = datetime.fromisoformat(sched)
            except (ValueError, TypeError):
                m.scheduled_date = None

        # Anything not finished goes back to waiting (an upload interrupted by
        # closing the app, or a status from the old version), unless the file is gone.
        if m.status != "done":
            if os.path.exists(path):
                if m.status != "error":
                    m.status = "ready"
                    m.error_message = ""
            else:
                m.status = "error"
                m.error_message = f"File not found: {path}"

        queue.append(m)

    print(f"[DataStore] Loaded {len(queue)} videos from {DATA_FILE}")
    return queue
