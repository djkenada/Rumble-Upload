from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class VideoMetadata:
    url: str = ""
    video_id: str = ""
    title: str = ""
    description: str = ""
    duration: int = 0
    duration_str: str = "00:00"
    thumbnail_url: str = ""
    tags: list[str] = field(default_factory=list)
    uploader: str = ""
    upload_date: str = ""
    local_file_path: str | None = None
    thumbnail_local_path: str | None = None
    scheduled_date: datetime | None = None
    status: str = "pending"  # pending, fetching, ready, downloading, uploading, done, error
    error_message: str = ""
