import customtkinter as ctk


class ProgressPanel(ctk.CTkFrame):
    """Compact single-row progress bars for download and upload."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(4, weight=1)

        # Download: label + bar + status
        ctk.CTkLabel(self, text="DL:", font=ctk.CTkFont(size=11), width=25).grid(
            row=0, column=0, padx=(10, 2), pady=5)
        self.download_bar = ctk.CTkProgressBar(self, height=12)
        self.download_bar.grid(row=0, column=1, sticky="ew", padx=2, pady=5)
        self.download_bar.set(0)
        self.download_status = ctk.CTkLabel(self, text="Idle", text_color="gray",
                                            font=ctk.CTkFont(size=10), width=180, anchor="w")
        self.download_status.grid(row=0, column=2, padx=2, pady=5)

        # Upload: label + bar + status
        ctk.CTkLabel(self, text="UL:", font=ctk.CTkFont(size=11), width=25).grid(
            row=0, column=3, padx=(10, 2), pady=5)
        self.upload_bar = ctk.CTkProgressBar(self, height=12)
        self.upload_bar.grid(row=0, column=4, sticky="ew", padx=2, pady=5)
        self.upload_bar.set(0)
        self.upload_status = ctk.CTkLabel(self, text="Idle", text_color="gray",
                                          font=ctk.CTkFont(size=10), width=180, anchor="w")
        self.upload_status.grid(row=0, column=5, padx=(2, 10), pady=5)

    def update_download(self, pct: float, status: str):
        self.download_bar.set(pct)
        self.download_status.configure(text=status[:30])

    def update_upload(self, pct: float, status: str):
        self.upload_bar.set(pct)
        self.upload_status.configure(text=status[:30])

    def reset(self):
        self.download_bar.set(0)
        self.download_status.configure(text="Idle")
        self.upload_bar.set(0)
        self.upload_status.configure(text="Idle")
