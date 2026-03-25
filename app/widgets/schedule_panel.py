import customtkinter as ctk
from datetime import datetime, timedelta

from app.widgets.date_time_picker import DateTimePicker


class SchedulePanel(ctk.CTkFrame):
    """Compact scheduling controls with date pickers. Central Time, AM/PM."""

    def __init__(self, master, on_apply=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_apply = on_apply

        # Row 0: Auto-schedule
        ctk.CTkLabel(self, text="Schedule:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(10, 5), pady=4)

        self.auto_picker = DateTimePicker(self)
        self.auto_picker.grid(row=0, column=1, padx=2, pady=4)

        ctk.CTkLabel(self, text="every").grid(row=0, column=2, padx=(8, 2), pady=4)

        self.interval_var = ctk.StringVar(value="24")
        self.interval_entry = ctk.CTkEntry(self, width=40, height=28, textvariable=self.interval_var)
        self.interval_entry.grid(row=0, column=3, padx=2, pady=4)

        self.interval_unit = ctk.CTkOptionMenu(self, values=["hours", "days"], width=70, height=28)
        self.interval_unit.grid(row=0, column=4, padx=2, pady=4)
        self.interval_unit.set("hours")

        self.auto_btn = ctk.CTkButton(self, text="Auto-Schedule", width=110, height=28,
                                      command=self._handle_auto_schedule)
        self.auto_btn.grid(row=0, column=5, padx=(8, 10), pady=4)

        # Row 1: Override selected
        ctk.CTkLabel(self, text="Override:", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=1, column=0, sticky="w", padx=(10, 5), pady=(0, 4))

        self.override_picker = DateTimePicker(self)
        self.override_picker.grid(row=1, column=1, padx=2, pady=(0, 4))

        self.override_btn = ctk.CTkButton(self, text="Set Selected", width=100, height=28,
                                          command=self._handle_override)
        self.override_btn.grid(row=1, column=5, padx=(8, 10), pady=(0, 4))

    def _handle_auto_schedule(self):
        if self._on_apply:
            self._on_apply("auto", self.get_auto_schedule_config())

    def _handle_override(self):
        if self._on_apply:
            dt = self.override_picker.get_datetime()
            if dt is None:
                self._on_apply("error", "Invalid date/time format")
            elif dt <= datetime.now():
                self._on_apply("error", "Date is in the past!")
            else:
                self._on_apply("override", dt)

    def get_auto_schedule_config(self) -> dict:
        start = self.auto_picker.get_datetime()
        if start is None or start <= datetime.now():
            start = datetime.now() + timedelta(days=1)
            start = start.replace(hour=10, minute=0, second=0, microsecond=0)

        try:
            interval_num = float(self.interval_var.get().strip())
        except ValueError:
            interval_num = 24

        unit = self.interval_unit.get()
        delta = timedelta(days=interval_num) if unit == "days" else timedelta(hours=interval_num)

        return {"start": start, "interval": delta}
