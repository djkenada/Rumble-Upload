import customtkinter as ctk


class ProgressPanel(ctk.CTkFrame):
    """Compact single-row progress bar for the current upload."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Upload:", font=ctk.CTkFont(size=11), width=50).grid(
            row=0, column=0, padx=(10, 2), pady=5)
        self.upload_bar = ctk.CTkProgressBar(self, height=12)
        self.upload_bar.grid(row=0, column=1, sticky="ew", padx=2, pady=5)
        self.upload_bar.set(0)
        self.upload_status = ctk.CTkLabel(self, text="Idle", text_color="gray",
                                          font=ctk.CTkFont(size=10), width=220, anchor="w")
        self.upload_status.grid(row=0, column=2, padx=(2, 10), pady=5)

    def update_upload(self, pct: float, status: str):
        self.upload_bar.set(pct)
        self.upload_status.configure(text=status[:40])

    def reset(self):
        self.upload_bar.set(0)
        self.upload_status.configure(text="Idle")
