import customtkinter as ctk


class URLInput(ctk.CTkFrame):
    """Input area for adding one or more YouTube URLs."""

    def __init__(self, master, on_add=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_add = on_add

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Add YouTube URLs (one per line)").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 0), columnspan=2
        )

        self.textbox = ctk.CTkTextbox(self, height=80)
        self.textbox.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        self.add_btn = ctk.CTkButton(self, text="Add to Queue", command=self._handle_add, width=120)
        self.add_btn.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="n")

    def _handle_add(self):
        text = self.textbox.get("1.0", "end").strip()
        if not text or not self._on_add:
            return
        urls = [line.strip() for line in text.splitlines() if line.strip()]
        if urls:
            self._on_add(urls)
            self.textbox.delete("1.0", "end")

    def set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.textbox.configure(state=state)
        self.add_btn.configure(state=state)
