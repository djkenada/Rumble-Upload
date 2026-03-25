import customtkinter as ctk
from PIL import Image
from datetime import datetime

from app.models.video_metadata import VideoMetadata


STATUS_COLORS = {
    "pending": "gray",
    "fetching": "yellow",
    "ready": "white",
    "downloading": "orange",
    "downloaded": "#22d3ee",
    "uploading": "cyan",
    "done": "green",
    "error": "red",
}


class VideoQueueItem(ctk.CTkFrame):
    """A single row in the video queue showing thumbnail, title, schedule, and status."""

    def __init__(self, master, metadata: VideoMetadata, on_select=None, on_remove=None, **kwargs):
        super().__init__(master, **kwargs)
        self.metadata = metadata
        self._on_select = on_select
        self._on_remove = on_remove
        self._thumb_image = None

        self.grid_columnconfigure(1, weight=1)
        self.configure(cursor="hand2", border_width=1, border_color="gray30")

        # Thumbnail
        self.thumb_label = ctk.CTkLabel(self, text="...", width=80, height=45)
        self.thumb_label.grid(row=0, column=0, rowspan=2, padx=5, pady=5)

        # Title
        self.title_label = ctk.CTkLabel(
            self, text=metadata.url if not metadata.title else metadata.title,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", justify="left", wraplength=300
        )
        self.title_label.grid(row=0, column=1, sticky="w", padx=5, pady=(5, 0))

        # Info row: duration + schedule + status
        self.info_label = ctk.CTkLabel(self, text="", anchor="w", text_color="gray", font=ctk.CTkFont(size=11))
        self.info_label.grid(row=1, column=1, sticky="w", padx=5, pady=(0, 5))

        # Status badge
        self.status_label = ctk.CTkLabel(
            self, text=metadata.status.upper(), width=80,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=STATUS_COLORS.get(metadata.status, "white")
        )
        self.status_label.grid(row=0, column=2, padx=5, pady=5)

        # Remove button
        self.remove_btn = ctk.CTkButton(
            self, text="X", width=30, height=30, fg_color="red", hover_color="darkred",
            command=self._handle_remove
        )
        self.remove_btn.grid(row=0, column=3, padx=5, pady=5)

        # Click to select
        for widget in [self, self.thumb_label, self.title_label, self.info_label]:
            widget.bind("<Button-1>", lambda e: self._handle_select())

        self.update_display()

    def _handle_select(self):
        if self._on_select:
            self._on_select(self.metadata)

    def _handle_remove(self):
        if self._on_remove:
            self._on_remove(self.metadata)

    def update_display(self):
        m = self.metadata
        self.title_label.configure(text=m.title if m.title else m.url)

        info_parts = []
        if m.duration_str and m.duration_str != "00:00":
            info_parts.append(m.duration_str)
        if m.scheduled_date:
            info_parts.append(f"Scheduled: {m.scheduled_date.strftime('%m/%d/%Y %I:%M %p')} CT")
        self.info_label.configure(text=" | ".join(info_parts) if info_parts else "")

        self.status_label.configure(
            text=m.status.upper(),
            text_color=STATUS_COLORS.get(m.status, "white")
        )

        if m.thumbnail_local_path:
            try:
                img = Image.open(m.thumbnail_local_path)
                img = img.resize((80, 45), Image.LANCZOS)
                self._thumb_image = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 45))
                self.thumb_label.configure(image=self._thumb_image, text="")
            except Exception:
                self.thumb_label.configure(text="[img]", image=None)

    def set_selected(self, selected: bool):
        if selected:
            self.configure(border_color="dodgerblue", border_width=2)
        else:
            self.configure(border_color="gray30", border_width=1)


class VideoQueue(ctk.CTkScrollableFrame):
    """Scrollable list of queued videos."""

    def __init__(self, master, on_select=None, on_remove=None, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._on_select = on_select
        self._on_remove = on_remove
        self._items: dict[str, VideoQueueItem] = {}  # keyed by url
        self._selected_url: str | None = None

    def add_video(self, metadata: VideoMetadata):
        item = VideoQueueItem(
            self, metadata,
            on_select=self._handle_select,
            on_remove=self._handle_remove,
        )
        item.grid(row=len(self._items), column=0, sticky="ew", pady=2)
        self._items[metadata.url] = item

    def remove_video(self, metadata: VideoMetadata):
        item = self._items.pop(metadata.url, None)
        if item:
            item.destroy()
        if self._selected_url == metadata.url:
            self._selected_url = None
        self._relayout()

    def update_video(self, metadata: VideoMetadata):
        item = self._items.get(metadata.url)
        if item:
            item.metadata = metadata
            item.update_display()

    def _handle_select(self, metadata: VideoMetadata):
        # Deselect previous
        if self._selected_url and self._selected_url in self._items:
            self._items[self._selected_url].set_selected(False)
        self._selected_url = metadata.url
        self._items[metadata.url].set_selected(True)
        if self._on_select:
            self._on_select(metadata)

    def _handle_remove(self, metadata: VideoMetadata):
        if self._on_remove:
            self._on_remove(metadata)

    def _relayout(self):
        for i, (url, item) in enumerate(self._items.items()):
            item.grid(row=i, column=0, sticky="ew", pady=2)

    def clear(self):
        for item in self._items.values():
            item.destroy()
        self._items.clear()
        self._selected_url = None
