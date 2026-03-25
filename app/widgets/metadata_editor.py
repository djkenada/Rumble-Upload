import customtkinter as ctk
from PIL import Image

from app.models.video_metadata import VideoMetadata


class MetadataEditor(ctk.CTkFrame):
    """Editor for the currently selected video's metadata."""

    def __init__(self, master, on_save=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_save = on_save
        self._current_url = None
        self._thumb_image = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        # Header
        ctk.CTkLabel(self, text="Edit Selected Video", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 5)
        )

        # Thumbnail
        self.thumb_label = ctk.CTkLabel(self, text="", width=120, height=68)
        self.thumb_label.grid(row=1, column=0, rowspan=2, padx=10, pady=5, sticky="n")

        # Title
        ctk.CTkLabel(self, text="Title:").grid(row=1, column=1, sticky="w", padx=5, pady=(5, 0))
        self.title_entry = ctk.CTkEntry(self, placeholder_text="Video title")
        self.title_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2, columnspan=2)

        # Description
        ctk.CTkLabel(self, text="Description:").grid(row=3, column=0, sticky="w", padx=10, pady=(5, 0), columnspan=3)
        self.desc_textbox = ctk.CTkTextbox(self, height=80)
        self.desc_textbox.grid(row=4, column=0, sticky="ew", padx=10, pady=2, columnspan=3)

        # Tags
        ctk.CTkLabel(self, text="Tags (comma-separated):").grid(row=5, column=0, sticky="w", padx=10, pady=(5, 0), columnspan=3)
        self.tags_entry = ctk.CTkEntry(self, placeholder_text="tag1, tag2, tag3")
        self.tags_entry.grid(row=6, column=0, sticky="ew", padx=10, pady=(2, 5), columnspan=3)

        # Save button
        self.save_btn = ctk.CTkButton(self, text="Save Changes", command=self._handle_save, width=120)
        self.save_btn.grid(row=7, column=0, padx=10, pady=(0, 10), sticky="w")

        self.status_label = ctk.CTkLabel(self, text="", text_color="green")
        self.status_label.grid(row=7, column=1, padx=5, pady=(0, 10), sticky="w")

    def set_metadata(self, metadata: VideoMetadata):
        self._current_url = metadata.url

        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, metadata.title)

        self.desc_textbox.delete("1.0", "end")
        self.desc_textbox.insert("1.0", metadata.description)

        self.tags_entry.delete(0, "end")
        if metadata.tags:
            self.tags_entry.insert(0, ", ".join(metadata.tags[:10]))

        # Thumbnail
        if metadata.thumbnail_local_path:
            try:
                img = Image.open(metadata.thumbnail_local_path)
                img = img.resize((120, 68), Image.LANCZOS)
                self._thumb_image = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 68))
                self.thumb_label.configure(image=self._thumb_image, text="")
            except Exception:
                self.thumb_label.configure(text="[No thumbnail]", image=None)
        else:
            self.thumb_label.configure(text="[No thumbnail]", image=None)

        self.status_label.configure(text="")

    def get_metadata_updates(self) -> dict:
        return {
            "url": self._current_url,
            "title": self.title_entry.get().strip(),
            "description": self.desc_textbox.get("1.0", "end").strip(),
            "tags": [t.strip() for t in self.tags_entry.get().split(",") if t.strip()],
        }

    def _handle_save(self):
        if self._on_save and self._current_url:
            self._on_save(self.get_metadata_updates())
            self.status_label.configure(text="Saved!")

    def clear(self):
        self._current_url = None
        self.title_entry.delete(0, "end")
        self.desc_textbox.delete("1.0", "end")
        self.tags_entry.delete(0, "end")
        self.thumb_label.configure(text="", image=None)
        self._thumb_image = None
        self.status_label.configure(text="")

    def set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.title_entry.configure(state=state)
        self.desc_textbox.configure(state=state)
        self.tags_entry.configure(state=state)
        self.save_btn.configure(state=state)
