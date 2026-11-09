import os
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from app.models.video_metadata import VideoMetadata


THUMBNAIL_FILE_TYPES = [
    ("Images", "*.jpg *.jpeg *.png"),
    ("All files", "*.*"),
]
THUMB_SIZE = (107, 60)  # 16:9 preview


class MetadataEditor(ctk.CTkFrame):
    """Editor for the currently selected video's metadata."""

    def __init__(self, master, on_save=None, on_thumbnail=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_save = on_save
        self._on_thumbnail = on_thumbnail  # called with (video_path, image_path), or (video_path, None) to remove
        self._current_path = None
        self._thumb_image = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        # Header
        ctk.CTkLabel(self, text="Edit Selected Video", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 5)
        )

        # Title
        ctk.CTkLabel(self, text="Title:").grid(row=1, column=0, sticky="w", padx=10, pady=(5, 0), columnspan=3)
        self.title_entry = ctk.CTkEntry(self, placeholder_text="Video title")
        self.title_entry.grid(row=2, column=0, sticky="ew", padx=10, pady=2, columnspan=3)

        # Description
        ctk.CTkLabel(self, text="Description:").grid(row=3, column=0, sticky="w", padx=10, pady=(5, 0), columnspan=3)
        # Short minimum so Save stays visible at the default window size; grows with the window
        self.desc_textbox = ctk.CTkTextbox(self, height=60)
        self.desc_textbox.grid(row=4, column=0, sticky="nsew", padx=10, pady=2, columnspan=3)
        self.grid_rowconfigure(4, weight=1)

        # Tags
        ctk.CTkLabel(self, text="Tags (comma-separated):").grid(row=5, column=0, sticky="w", padx=10, pady=(5, 0), columnspan=3)
        self.tags_entry = ctk.CTkEntry(self, placeholder_text="tag1, tag2, tag3")
        self.tags_entry.grid(row=6, column=0, sticky="ew", padx=10, pady=(2, 5), columnspan=3)

        # Thumbnail: preview on the left, attach/remove controls beside it
        thumb_row = ctk.CTkFrame(self, fg_color="transparent")
        thumb_row.grid(row=8, column=0, sticky="ew", padx=10, pady=(4, 8), columnspan=3)
        thumb_row.grid_columnconfigure(1, weight=1)

        self.thumb_label = ctk.CTkLabel(thumb_row, text="[No thumbnail]", width=THUMB_SIZE[0], height=THUMB_SIZE[1],
                                        fg_color="gray20", corner_radius=4, text_color="gray")
        self.thumb_label.grid(row=0, column=0, rowspan=2, sticky="w")

        thumb_btns = ctk.CTkFrame(thumb_row, fg_color="transparent")
        thumb_btns.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.thumb_btn = ctk.CTkButton(thumb_btns, text="Attach Thumbnail", width=130,
                                       command=self._handle_attach_thumbnail)
        self.thumb_btn.grid(row=0, column=0)
        self.thumb_clear_btn = ctk.CTkButton(thumb_btns, text="Remove", width=70,
                                             fg_color="#475569", hover_color="#334155",
                                             command=self._handle_remove_thumbnail)
        self.thumb_clear_btn.grid(row=0, column=1, padx=(6, 0))

        self.thumb_name_label = ctk.CTkLabel(thumb_row, text="", anchor="w", text_color="gray",
                                             font=ctk.CTkFont(size=11))
        self.thumb_name_label.grid(row=1, column=1, sticky="w", padx=(10, 0))

        # Save button
        self.save_btn = ctk.CTkButton(self, text="Save Changes", command=self._handle_save, width=120)
        self.save_btn.grid(row=9, column=0, padx=10, pady=(0, 10), sticky="w")

        self.status_label = ctk.CTkLabel(self, text="", text_color="green")
        self.status_label.grid(row=9, column=1, padx=5, pady=(0, 10), sticky="w")

    def _show_thumbnail(self, path: str | None) -> bool:
        """Show the image at path in the preview. Returns False if it can't be read."""
        if path:
            try:
                img = Image.open(path)
                img = img.resize(THUMB_SIZE, Image.LANCZOS)
                self._thumb_image = ctk.CTkImage(light_image=img, dark_image=img, size=THUMB_SIZE)
                self.thumb_label.configure(image=self._thumb_image, text="")
                self.thumb_name_label.configure(text=os.path.basename(path))
                return True
            except Exception:
                pass
        self._thumb_image = None
        self.thumb_label.configure(text="[No thumbnail]", image=None)
        self.thumb_name_label.configure(text="")
        return False

    def _handle_attach_thumbnail(self):
        if not self._current_path:
            self.status_label.configure(text="Select a video first.", text_color="orange")
            return
        path = filedialog.askopenfilename(
            parent=self, title="Select a thumbnail image", filetypes=THUMBNAIL_FILE_TYPES
        )
        if not path:
            return
        path = os.path.normpath(path)
        try:
            with Image.open(path) as img:
                img.verify()
        except Exception:
            self.status_label.configure(text="That file is not a readable image.", text_color="red")
            return
        # Applies immediately, so it doesn't depend on Save Changes
        if self._on_thumbnail:
            self._on_thumbnail(self._current_path, path)
        self._show_thumbnail(path)
        self.status_label.configure(text="Thumbnail attached.", text_color="green")

    def _handle_remove_thumbnail(self):
        if not self._current_path:
            return
        if self._on_thumbnail:
            self._on_thumbnail(self._current_path, None)
        self._show_thumbnail(None)
        self.status_label.configure(text="Thumbnail removed.", text_color="green")

    def set_metadata(self, metadata: VideoMetadata):
        self._current_path = metadata.local_file_path

        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, metadata.title)

        self.desc_textbox.delete("1.0", "end")
        self.desc_textbox.insert("1.0", metadata.description)

        self.tags_entry.delete(0, "end")
        if metadata.tags:
            self.tags_entry.insert(0, ", ".join(metadata.tags[:10]))

        self._show_thumbnail(metadata.thumbnail_local_path)

        self.status_label.configure(text="")

    def get_metadata_updates(self) -> dict:
        return {
            "path": self._current_path,
            "title": self.title_entry.get().strip(),
            "description": self.desc_textbox.get("1.0", "end").strip(),
            "tags": [t.strip() for t in self.tags_entry.get().split(",") if t.strip()],
        }

    def _handle_save(self):
        if self._on_save and self._current_path:
            self._on_save(self.get_metadata_updates())
            self.status_label.configure(text="Saved!", text_color="green")

    def clear(self):
        self._current_path = None
        self.title_entry.delete(0, "end")
        self.desc_textbox.delete("1.0", "end")
        self.tags_entry.delete(0, "end")
        self._show_thumbnail(None)
        self.status_label.configure(text="")

    def set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.title_entry.configure(state=state)
        self.desc_textbox.configure(state=state)
        self.tags_entry.configure(state=state)
        self.save_btn.configure(state=state)
        self.thumb_btn.configure(state=state)
        self.thumb_clear_btn.configure(state=state)
