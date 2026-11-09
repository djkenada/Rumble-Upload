from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class VideoMetadata:
    # Path of the video file on disk. This is the queue's unique key. The file
    # belongs to the user and the app never deletes it.
    local_file_path: str = ""
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    category: str = "News"  # one of config.RUMBLE_CATEGORIES
    # Optional image the user attached; also never deleted by the app.
    thumbnail_local_path: str | None = None
    scheduled_date: datetime | None = None
    status: str = "ready"  # ready, uploading, done, error
    error_message: str = ""
