import datetime
import os
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from app.models.video_metadata import VideoMetadata
from app.services import rumble_service
from app.services.data_store import save_queue, load_queue
from app.utils.threading_utils import run_in_thread, ThreadSafeCallback
from app.widgets.video_queue import VideoQueue
from app.widgets.metadata_editor import MetadataEditor
from app.widgets.schedule_panel import SchedulePanel
from app.widgets.progress_panel import ProgressPanel


VIDEO_FILE_TYPES = [
    ("Video files", "*.mp4 *.mov *.mkv *.webm *.avi *.m4v *.wmv *.flv *.mpg *.mpeg *.ts"),
    ("All files", "*.*"),
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Rumble Uploader")
        self.geometry("900x900")
        self.minsize(800, 650)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._queue: list[VideoMetadata] = []
        self._selected: VideoMetadata | None = None
        self._driver = None
        self._chrome_proc = None
        self._processing = False

        # Thread-safe callback system for progress updates
        self._callbacks = ThreadSafeCallback(self, poll_interval=100)
        self._callbacks.start_polling()

        self._build_ui()
        self._load_saved_data()
        self._log("App started. Click 'Open Browser' and log into Rumble, then 'Add Video Files'.")

    def _build_ui(self):
        # Single column layout with sections
        self.grid_columnconfigure(0, weight=1)

        row = 0

        # ---- Header ----
        header = ctk.CTkLabel(self, text="Rumble Uploader",
                              font=ctk.CTkFont(size=20, weight="bold"))
        header.grid(row=row, column=0, padx=20, pady=(10, 5))
        row += 1

        # ---- Action buttons ----
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=row, column=0, sticky="ew", padx=10, pady=5)
        btn_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.chrome_btn = ctk.CTkButton(btn_frame, text="Open Browser",
                                        command=self._on_open_chrome, height=35)
        self.chrome_btn.grid(row=0, column=0, padx=3, pady=8)

        self.login_status = ctk.CTkLabel(btn_frame, text="Not connected", text_color="orange")
        self.login_status.grid(row=0, column=1, padx=3, pady=8)

        self.add_btn = ctk.CTkButton(btn_frame, text="Add Video Files", height=35,
                                     command=self._on_browse_files,
                                     fg_color="#2563eb", hover_color="#1d4ed8")
        self.add_btn.grid(row=0, column=2, padx=3, pady=8)

        self.upload_btn = ctk.CTkButton(btn_frame, text="Upload All", height=35,
                                        command=self._on_upload_all,
                                        fg_color="green", hover_color="darkgreen")
        self.upload_btn.grid(row=0, column=3, padx=3, pady=8)

        self.stop_btn = ctk.CTkButton(btn_frame, text="Stop", height=35,
                                      command=self._on_stop,
                                      fg_color="red", hover_color="darkred", state="disabled")
        self.stop_btn.grid(row=0, column=4, padx=3, pady=8)
        row += 1

        # ---- Progress bar ----
        self.progress_panel = ProgressPanel(self)
        self.progress_panel.grid(row=row, column=0, sticky="ew", padx=10, pady=3)
        row += 1

        # ---- Middle section: resizable paned window (queue | editor) ----
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED,
                               bg="#333333", bd=0)
        paned.grid(row=row, column=0, sticky="nsew", padx=10, pady=3)
        self.grid_rowconfigure(row, weight=1)

        # Queue (left pane)
        queue_frame = ctk.CTkFrame(paned)
        queue_frame.grid_columnconfigure(0, weight=1)
        queue_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(queue_frame, text="Video Queue", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(5, 0))
        self.video_queue = VideoQueue(queue_frame, on_select=self._on_select_video,
                                      on_remove=self._on_remove_video)
        self.video_queue.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        paned.add(queue_frame, minsize=250, stretch="always")

        # Editor (right pane)
        self.metadata_editor = MetadataEditor(paned, on_save=self._on_save_metadata,
                                              on_thumbnail=self._on_set_thumbnail)
        paned.add(self.metadata_editor, minsize=250, stretch="always")
        row += 1

        # ---- Schedule panel ----
        self.schedule_panel = SchedulePanel(self, on_apply=self._on_schedule_apply)
        self.schedule_panel.grid(row=row, column=0, sticky="ew", padx=10, pady=3)
        row += 1

        # ---- Log area ----
        ctk.CTkLabel(self, text="Log", anchor="w").grid(
            row=row, column=0, sticky="w", padx=15, pady=(3, 0))
        row += 1
        self.log_box = ctk.CTkTextbox(self, height=100, state="disabled")
        self.log_box.grid(row=row, column=0, sticky="ew", padx=10, pady=(0, 10))

    # ---- Data persistence ----
    def _load_saved_data(self):
        """Load previously saved queue on startup."""
        saved = load_queue()
        if saved:
            self._queue = saved
            for m in saved:
                self.video_queue.add_video(m)
            self._log(f"Restored {len(saved)} video(s) from previous session.")
        # Start auto-save timer
        self._auto_save()

    def _save_data(self):
        """Save current queue to disk."""
        try:
            save_queue(self._queue)
        except Exception as e:
            print(f"[Save Error] {e}")

    def _auto_save(self):
        """Auto-save queue every 10 seconds."""
        if self._queue:
            self._save_data()
        self.after(10000, self._auto_save)

    # ---- Logging ----
    def _log(self, message: str):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        # Also print to console for debugging
        try:
            print(f"[LOG {timestamp}] {message}")
        except Exception:
            pass

    def _find(self, path: str) -> VideoMetadata | None:
        for m in self._queue:
            if m.local_file_path == path:
                return m
        return None

    # ---- Add video files ----
    def _on_browse_files(self):
        paths = filedialog.askopenfilenames(
            parent=self, title="Select video files to upload", filetypes=VIDEO_FILE_TYPES
        )
        if paths:
            self._on_add_files(list(paths))

    def _on_add_files(self, paths: list[str]):
        """Queue video files from disk, ready to upload."""
        added = 0
        for raw in paths:
            path = os.path.normpath(os.path.abspath(raw))
            if not os.path.isfile(path):
                self._log(f"Skipping (not a file): {path}")
                continue
            if self._find(path):
                self._log(f"Skipping duplicate: {path}")
                continue
            metadata = VideoMetadata(
                local_file_path=path,
                title=os.path.splitext(os.path.basename(path))[0],
                status="ready",
            )
            self._queue.append(metadata)
            self.video_queue.add_video(metadata)
            self._log(f"Added: {path}")
            added += 1

        if added:
            self._log(f"{added} video(s) ready. Edit the title/description, then click 'Upload All'.")

    # ---- Queue management ----
    def _on_select_video(self, metadata: VideoMetadata):
        self._selected = metadata
        self.metadata_editor.set_metadata(metadata)

    def _on_remove_video(self, metadata: VideoMetadata):
        # Only the queue entry goes away; the video and thumbnail files are the user's
        self._queue = [m for m in self._queue if m is not metadata]
        self.video_queue.remove_video(metadata)
        if self._selected is metadata:
            self._selected = None
            self.metadata_editor.clear()
        self._log(f"Removed: {metadata.title or metadata.local_file_path}")
        # Persist now so an emptied queue doesn't come back on restart
        self._save_data()

    def _on_save_metadata(self, updates: dict):
        m = self._find(updates["path"])
        if m:
            m.title = updates["title"]
            m.description = updates["description"]
            m.tags = updates["tags"]
            self.video_queue.update_video(m)
            self._log(f"Saved: {m.title}")

    def _on_set_thumbnail(self, video_path: str, image_path: str | None):
        """Attach a thumbnail image to a video, or remove it when image_path is None."""
        m = self._find(video_path)
        if not m:
            return
        m.thumbnail_local_path = image_path
        self.video_queue.update_video(m)
        if image_path:
            self._log(f"Thumbnail attached to '{m.title}': {image_path}")
        else:
            self._log(f"Thumbnail removed from '{m.title}'")

    # ---- Scheduling ----
    def _on_schedule_apply(self, mode: str, data):
        if mode == "error":
            self._log(f"Schedule error: {data}")
            return
        if mode == "auto":
            config = data
            start = config["start"]
            interval = config["interval"]
            videos = [m for m in self._queue if m.status == "ready"]
            for i, m in enumerate(videos):
                m.scheduled_date = start + (interval * i)
                self.video_queue.update_video(m)
            self._log(f"Scheduled {len(videos)} videos from {start.strftime('%Y-%m-%d %H:%M')}")
        elif mode == "override":
            if self._selected:
                self._selected.scheduled_date = data
                self.video_queue.update_video(self._selected)
                self._log(f"Scheduled '{self._selected.title}': {data.strftime('%Y-%m-%d %H:%M')}")
            else:
                self._log("No video selected.")

    # ---- Chrome / Rumble ----
    def _on_open_chrome(self):
        self._log("Launching Chrome...")
        try:
            self._chrome_proc = rumble_service.launch_chrome()
            self._log("Chrome launched. Log into Rumble there, then come back and upload.")
            self.login_status.configure(text="Chrome launched", text_color="yellow")
        except Exception as e:
            self._log(f"Chrome error: {e}")

    def _connect_to_chrome(self) -> bool:
        """Attach to the Chrome window. Called from the upload thread, so UI updates go through after()."""
        try:
            if self._driver:
                try:
                    self._driver.title
                    return True
                except Exception:
                    self._driver = None
            self._driver = rumble_service.connect()
            self.after(0, lambda: self.login_status.configure(text="Connected", text_color="green"))
            return True
        except Exception as e:
            self.after(0, lambda err=e: self._log(f"Chrome connection failed: {err}"))
            return False

    # ---- Upload ----
    def _set_processing(self, processing: bool):
        self._processing = processing
        self.upload_btn.configure(state="disabled" if processing else "normal")
        self.stop_btn.configure(state="normal" if processing else "disabled")

    def _on_upload_all(self):
        # Give failed uploads another try when the file is still there
        for m in self._queue:
            if m.status == "error" and os.path.exists(m.local_file_path):
                m.status = "ready"
                m.error_message = ""
                self.video_queue.update_video(m)

        uploadable = [m for m in self._queue if m.status == "ready"]
        if not uploadable:
            self._log("Nothing to upload. Click 'Add Video Files' first.")
            return

        self._set_processing(True)
        self._log(f"Uploading {len(uploadable)} video(s)...")
        self._process_next()

    def _on_stop(self):
        self._set_processing(False)
        self._log("Stopped. The upload already in progress will finish; no more will start.")

    def _process_next(self):
        if not self._processing:
            return

        for m in self._queue:
            if m.status == "ready":
                self._upload_to_rumble(m)
                return

        self._set_processing(False)
        self._log("All done!")

    def _upload_to_rumble(self, metadata: VideoMetadata):
        metadata.status = "uploading"
        self.video_queue.update_video(metadata)
        self.progress_panel.reset()
        self._log(f"Uploading: {metadata.title}")

        def do_upload():
            if not self._connect_to_chrome():
                raise RuntimeError("Could not connect to Chrome. Click 'Open Browser' first.")
            if not rumble_service.check_login_status(self._driver):
                raise RuntimeError("Not logged into Rumble. Log in in the Chrome window, then click 'Upload All' again.")

            def ul_progress(pct, status):
                self._callbacks.schedule(
                    lambda p=pct, s=status: self.progress_panel.update_upload(p, s)
                )
            rumble_service.upload_video(self._driver, metadata, ul_progress)

        def on_done(_):
            metadata.status = "done"
            self.video_queue.update_video(metadata)
            self.progress_panel.update_upload(1.0, "Complete!")
            self._log(f"Uploaded: {metadata.title}")
            self.after(2000, self._process_next)

        def on_error(err):
            metadata.status = "error"
            metadata.error_message = str(err)
            self.video_queue.update_video(metadata)
            self._log(f"Upload error: {err}")
            self.after(1000, self._process_next)

        run_in_thread(self, do_upload, on_done, on_error)

    def on_closing(self):
        self._processing = False
        self._callbacks.stop_polling()
        self._save_data()
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
        self.destroy()
