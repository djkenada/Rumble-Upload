import datetime
import traceback
import customtkinter as ctk

from app.models.video_metadata import VideoMetadata
from app.services import youtube_service, rumble_service, file_manager
from app.services.cookie_helper import export_cookies_from_selenium, cookie_file_exists
from app.services.data_store import save_queue, load_queue
from app.utils.threading_utils import run_in_thread, ThreadSafeCallback
from app.widgets.url_input import URLInput
from app.widgets.video_queue import VideoQueue
from app.widgets.metadata_editor import MetadataEditor
from app.widgets.schedule_panel import SchedulePanel
from app.widgets.progress_panel import ProgressPanel


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube to Rumble Uploader")
        self.geometry("900x950")
        self.minsize(800, 700)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._queue: list[VideoMetadata] = []
        self._selected: VideoMetadata | None = None
        self._driver = None
        self._chrome_proc = None
        self._processing = False
        self._upload_after_download = False
        self._upload_only = False

        # Thread-safe callback system for progress updates
        self._callbacks = ThreadSafeCallback(self, poll_interval=100)
        self._callbacks.start_polling()

        self._build_ui()
        self._load_saved_data()
        self._log("App started. Add YouTube URLs and click 'Add to Queue'.")

    def _build_ui(self):
        # Single column layout with sections
        self.grid_columnconfigure(0, weight=1)

        row = 0

        # ---- Header ----
        header = ctk.CTkLabel(self, text="YouTube to Rumble Uploader",
                              font=ctk.CTkFont(size=20, weight="bold"))
        header.grid(row=row, column=0, padx=20, pady=(10, 5))
        row += 1

        # ---- URL input ----
        self.url_input = URLInput(self, on_add=self._on_add_urls)
        self.url_input.grid(row=row, column=0, sticky="ew", padx=10, pady=3)
        row += 1

        # ---- Action buttons (RIGHT BELOW URL INPUT so they're always visible) ----
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=row, column=0, sticky="ew", padx=10, pady=5)

        # Row 0: Browser controls
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.chrome_btn = ctk.CTkButton(btn_frame, text="Open Browser",
                                        command=self._on_open_chrome, height=35)
        self.chrome_btn.grid(row=0, column=0, padx=3, pady=5)

        self.cookie_btn = ctk.CTkButton(btn_frame, text="Get YT Cookies",
                                        command=self._on_get_cookies, height=35,
                                        fg_color="#f59e0b", hover_color="#d97706",
                                        text_color="black")
        self.cookie_btn.grid(row=0, column=1, padx=3, pady=5)

        self.login_status = ctk.CTkLabel(btn_frame, text="Not connected", text_color="orange")
        self.login_status.grid(row=0, column=2, padx=3, pady=5)

        # Row 1: Action buttons
        btn_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.download_btn = ctk.CTkButton(btn_frame, text="Download All", height=35,
                                          command=self._on_download_all,
                                          fg_color="#2563eb", hover_color="#1d4ed8")
        self.download_btn.grid(row=1, column=0, padx=3, pady=5)

        self.upload_btn = ctk.CTkButton(btn_frame, text="Upload All", height=35,
                                        command=self._on_upload_all,
                                        fg_color="#7c3aed", hover_color="#6d28d9")
        self.upload_btn.grid(row=1, column=1, padx=3, pady=5)

        self.start_btn = ctk.CTkButton(btn_frame, text="DL & Upload", height=35,
                                       command=self._on_start_all,
                                       fg_color="green", hover_color="darkgreen")
        self.start_btn.grid(row=1, column=2, padx=3, pady=5)

        self.stop_btn = ctk.CTkButton(btn_frame, text="Stop", height=35,
                                      command=self._on_stop,
                                      fg_color="red", hover_color="darkred", state="disabled")
        self.stop_btn.grid(row=1, column=3, padx=3, pady=5)
        row += 1

        # ---- Progress bars ----
        self.progress_panel = ProgressPanel(self)
        self.progress_panel.grid(row=row, column=0, sticky="ew", padx=10, pady=3)
        row += 1

        # ---- Middle section: resizable paned window (queue | editor) ----
        import tkinter as tk
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
        self.metadata_editor = MetadataEditor(paned, on_save=self._on_save_metadata)
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

    # ---- Add URLs ----
    def _on_add_urls(self, urls: list[str]):
        for url in urls:
            if any(m.url == url for m in self._queue):
                self._log(f"Skipping duplicate: {url}")
                continue
            metadata = VideoMetadata(url=url, status="pending")
            self._queue.append(metadata)
            self.video_queue.add_video(metadata)
            self._log(f"Added: {url}")

        # Start sequential fetch
        self._fetch_next_pending()

    def _fetch_next_pending(self):
        """Fetch info for the next pending video (one at a time to avoid bot detection)."""
        # Check if a fetch is already running
        if any(m.status == "fetching" for m in self._queue):
            return

        # Find next pending
        next_meta = None
        for m in self._queue:
            if m.status == "pending":
                next_meta = m
                break

        if not next_meta:
            return  # All done

        next_meta.status = "fetching"
        self.video_queue.update_video(next_meta)
        self._log(f"Fetching: {next_meta.url}")

        def do_fetch():
            return youtube_service.fetch_info(next_meta.url)

        def on_done(result: VideoMetadata):
            next_meta.video_id = result.video_id
            next_meta.title = result.title
            next_meta.description = result.description
            next_meta.duration = result.duration
            next_meta.duration_str = result.duration_str
            next_meta.thumbnail_url = result.thumbnail_url
            next_meta.tags = result.tags
            next_meta.uploader = result.uploader
            next_meta.upload_date = result.upload_date
            next_meta.thumbnail_local_path = result.thumbnail_local_path
            next_meta.status = "ready"
            self.video_queue.update_video(next_meta)
            self._log(f"Ready: {next_meta.title} ({next_meta.duration_str})")
            if self._selected and self._selected.url == next_meta.url:
                self.metadata_editor.set_metadata(next_meta)
            # Fetch the next one after a short delay
            self.after(1000, self._fetch_next_pending)

        def on_error(err: Exception):
            next_meta.status = "error"
            next_meta.error_message = str(err)
            self.video_queue.update_video(next_meta)
            self._log(f"Fetch error: {err}")
            # Continue to next after delay
            self.after(2000, self._fetch_next_pending)

        run_in_thread(self, do_fetch, on_done, on_error)

    # ---- Queue management ----
    def _on_select_video(self, metadata: VideoMetadata):
        self._selected = metadata
        self.metadata_editor.set_metadata(metadata)

    def _on_remove_video(self, metadata: VideoMetadata):
        self._queue = [m for m in self._queue if m.url != metadata.url]
        self.video_queue.remove_video(metadata)
        if self._selected and self._selected.url == metadata.url:
            self._selected = None
            self.metadata_editor.clear()
        file_manager.cleanup_file(metadata.local_file_path)
        file_manager.cleanup_file(metadata.thumbnail_local_path)
        self._log(f"Removed: {metadata.title or metadata.url}")

    def _on_save_metadata(self, updates: dict):
        for m in self._queue:
            if m.url == updates["url"]:
                m.title = updates["title"]
                m.description = updates["description"]
                m.tags = updates["tags"]
                self.video_queue.update_video(m)
                self._log(f"Saved: {m.title}")
                break

    # ---- Scheduling ----
    def _on_schedule_apply(self, mode: str, data):
        if mode == "error":
            self._log(f"Schedule error: {data}")
            return
        if mode == "auto":
            config = data
            start = config["start"]
            interval = config["interval"]
            videos = [m for m in self._queue if m.status in ("ready", "pending", "fetching", "downloaded")]
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
            self._log("Chrome launched. Log into Rumble AND YouTube, then click 'Get YT Cookies'.")
            self.login_status.configure(text="Chrome launched", text_color="yellow")
        except Exception as e:
            self._log(f"Chrome error: {e}")

    def _on_get_cookies(self):
        """Extract YouTube cookies from the Chrome debug session."""
        self._log("Getting YouTube cookies...")
        self.cookie_btn.configure(state="disabled", text="Getting cookies...")

        def do_cookies():
            if not self._connect_to_chrome_sync():
                raise Exception("Open the browser first, then log into YouTube.")
            return export_cookies_from_selenium(self._driver)

        def on_done(path):
            self._log(f"YouTube cookies saved! You can now fetch videos.")
            self.cookie_btn.configure(state="normal", fg_color="#22c55e", text_color="white", text="Get YT Cookies")

        def on_error(err):
            self._log(f"Cookie error: {err}")
            self.cookie_btn.configure(state="normal", text="Get YT Cookies")

        run_in_thread(self, do_cookies, on_done, on_error)

    def _connect_to_chrome_sync(self) -> bool:
        """Connect to Chrome - safe to call from background thread."""
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
        except Exception:
            return False

    def _connect_to_chrome(self) -> bool:
        try:
            if self._driver:
                try:
                    self._driver.title
                    return True
                except Exception:
                    self._driver = None
            self._driver = rumble_service.connect()
            self.login_status.configure(text="Connected", text_color="green")
            return True
        except Exception as e:
            self._log(f"Chrome connection failed: {e}")
            return False

    # ---- Download Only ----
    def _on_download_all(self):
        self._log(f"Download All clicked. {len(self._queue)} video(s) in queue.")
        for m in self._queue:
            self._log(f"  [{m.status}] {m.title or m.url[:60]}")

        ready = [m for m in self._queue if m.status == "ready"]
        if not ready:
            fetching = [m for m in self._queue if m.status == "fetching"]
            if fetching:
                self._log(f"Still fetching {len(fetching)} video(s). Wait for READY status.")
            else:
                self._log("No videos ready. Add URLs first.")
            return

        self._processing = True
        self._upload_after_download = False
        self.download_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._log(f"Downloading {len(ready)} video(s)...")
        self._process_next()

    # ---- Upload Only (for already downloaded videos) ----
    def _on_upload_all(self):
        uploadable = [m for m in self._queue if m.status == "downloaded" and m.local_file_path]
        self._log(f"Upload All clicked. {len(uploadable)} downloaded video(s) to upload.")
        if not uploadable:
            self._log("No downloaded videos to upload. Download first.")
            return

        self._processing = True
        self._upload_only = True
        self._upload_after_download = False
        self.download_btn.configure(state="disabled")
        self.upload_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._log(f"Uploading {len(uploadable)} video(s)...")
        self._process_next()

    # ---- Download & Upload ----
    def _on_start_all(self):
        self._log(f"Download & Upload clicked. {len(self._queue)} video(s) in queue.")
        actionable = [m for m in self._queue if m.status in ("ready", "downloaded")]
        if not actionable:
            fetching = [m for m in self._queue if m.status == "fetching"]
            if fetching:
                self._log(f"Still fetching {len(fetching)} video(s). Wait for READY status.")
            else:
                self._log("No videos ready. Add URLs first.")
            return

        self._processing = True
        self._upload_after_download = True
        self._upload_only = False
        self.download_btn.configure(state="disabled")
        self.upload_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._log(f"Processing {len(actionable)} video(s)...")
        self._process_next()

    def _on_stop(self):
        self._processing = False
        self.download_btn.configure(state="normal")
        self.upload_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._log("Stopped.")

    def _process_next(self):
        if not self._processing:
            return

        next_video = None

        # Upload-only mode: find downloaded videos
        if getattr(self, '_upload_only', False):
            for m in self._queue:
                if m.status == "downloaded" and m.local_file_path:
                    next_video = m
                    break
            if next_video:
                self._upload_to_rumble(next_video)
                return
        else:
            # Normal mode: find ready videos to download (or downloaded to upload)
            for m in self._queue:
                if m.status == "ready":
                    next_video = m
                    break
            if next_video:
                self._download_video(next_video)
                return

            # If uploading after download, check for downloaded videos too
            if self._upload_after_download:
                for m in self._queue:
                    if m.status == "downloaded" and m.local_file_path:
                        next_video = m
                        break
                if next_video:
                    self._upload_to_rumble(next_video)
                    return

        # Nothing left to process
        self._processing = False
        self._upload_only = False
        self.download_btn.configure(state="normal")
        self.upload_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._log("All done!")
        return

    def _download_video(self, metadata: VideoMetadata):
        metadata.status = "downloading"
        self.video_queue.update_video(metadata)
        self.progress_panel.reset()
        self._log(f"Downloading: {metadata.title}")

        def do_download():
            def dl_progress(pct, status):
                self._callbacks.schedule(
                    lambda p=pct, s=status: self.progress_panel.update_download(p, s)
                )
            print(f"[THREAD] Starting download: {metadata.title}")
            path = youtube_service.download_video(metadata, dl_progress)
            print(f"[THREAD] Download complete: {path}")
            return path

        def on_done(file_path):
            self._log(f"Downloaded: {metadata.title}")
            self.progress_panel.update_download(1.0, "Complete!")
            if self._upload_after_download:
                self._upload_to_rumble(metadata)
            else:
                metadata.status = "downloaded"
                self.video_queue.update_video(metadata)
                self.after(500, self._process_next)

        def on_error(err):
            metadata.status = "error"
            metadata.error_message = str(err)
            self.video_queue.update_video(metadata)
            self._log(f"Download error: {err}")
            self.after(1000, self._process_next)

        run_in_thread(self, do_download, on_done, on_error)

    def _upload_to_rumble(self, metadata: VideoMetadata):
        metadata.status = "uploading"
        self.video_queue.update_video(metadata)
        self._log(f"Uploading: {metadata.title}")

        def do_upload():
            if not self._connect_to_chrome():
                raise RuntimeError("Connect to Chrome first.")
            if not rumble_service.check_login_status(self._driver):
                raise RuntimeError("Not logged into Rumble.")

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
            file_manager.cleanup_file(metadata.local_file_path)
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
        # Don't cleanup downloaded files - we want to keep them!
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
        self.destroy()
