import customtkinter as ctk
from tkcalendar import Calendar
from datetime import datetime, timedelta
import tkinter as tk


class TimePicker(tk.Toplevel):
    """Popup time picker with hour/minute spinboxes and AM/PM."""

    def __init__(self, parent, initial_hour=10, initial_minute=0, initial_ampm="AM", on_select=None):
        super().__init__(parent)
        self.title("Select Time")
        self.geometry("220x160")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._on_select = on_select

        self.configure(bg="#2b2b2b")

        # Header
        tk.Label(self, text="Select Time", font=("Arial", 12, "bold"),
                 bg="#2b2b2b", fg="white").pack(pady=(10, 5))

        # Spinner frame
        frame = tk.Frame(self, bg="#2b2b2b")
        frame.pack(pady=5)

        # Hour spinner
        tk.Label(frame, text="Hour", bg="#2b2b2b", fg="gray", font=("Arial", 9)).grid(row=0, column=0, padx=5)
        self.hour_var = tk.StringVar(value=str(initial_hour))
        self.hour_spin = tk.Spinbox(frame, from_=1, to=12, width=3, font=("Arial", 16),
                                     textvariable=self.hour_var, justify="center",
                                     bg="#3b3b3b", fg="white", buttonbackground="#555")
        self.hour_spin.grid(row=1, column=0, padx=5)

        tk.Label(frame, text=":", bg="#2b2b2b", fg="white", font=("Arial", 16, "bold")).grid(row=1, column=1)

        # Minute spinner
        tk.Label(frame, text="Min", bg="#2b2b2b", fg="gray", font=("Arial", 9)).grid(row=0, column=2, padx=5)
        self.min_var = tk.StringVar(value=f"{initial_minute:02d}")
        self.min_spin = tk.Spinbox(frame, from_=0, to=59, width=3, font=("Arial", 16),
                                    textvariable=self.min_var, justify="center", format="%02.0f",
                                    bg="#3b3b3b", fg="white", buttonbackground="#555")
        self.min_spin.grid(row=1, column=2, padx=5)

        # AM/PM toggle
        tk.Label(frame, text="", bg="#2b2b2b").grid(row=0, column=3)
        self.ampm_var = tk.StringVar(value=initial_ampm)
        self.ampm_btn = tk.Button(frame, textvariable=self.ampm_var, width=3, font=("Arial", 14, "bold"),
                                   command=self._toggle_ampm, bg="#2563eb", fg="white",
                                   activebackground="#1d4ed8", activeforeground="white", relief="flat")
        self.ampm_btn.grid(row=1, column=3, padx=8)

        # OK button
        tk.Button(self, text="OK", command=self._confirm, width=10,
                  bg="#22c55e", fg="white", font=("Arial", 11, "bold"),
                  activebackground="#16a34a", relief="flat").pack(pady=10)

    def _toggle_ampm(self):
        self.ampm_var.set("PM" if self.ampm_var.get() == "AM" else "AM")

    def _confirm(self):
        try:
            h = int(self.hour_var.get())
            m = int(self.min_var.get())
            ampm = self.ampm_var.get()
            if self._on_select:
                self._on_select(h, m, ampm)
        except ValueError:
            pass
        self.destroy()


class DateTimePicker(ctk.CTkFrame):
    """Compact date + time picker with calendar and time popups."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        # Date button (opens calendar)
        self.date_var = ctk.StringVar()
        self.date_btn = ctk.CTkButton(self, textvariable=self.date_var, width=95, height=28,
                                      fg_color="gray25", hover_color="gray35",
                                      command=self._open_calendar)
        self.date_btn.grid(row=0, column=0, padx=(0, 2))

        # Time button (opens time picker)
        self.time_var = ctk.StringVar(value="10:00 AM")
        self.time_btn = ctk.CTkButton(self, textvariable=self.time_var, width=85, height=28,
                                      fg_color="gray25", hover_color="gray35",
                                      command=self._open_time_picker)
        self.time_btn.grid(row=0, column=1, padx=(2, 0))

        self._cal_window = None
        self._time_window = None
        self._hour = 10
        self._minute = 0
        self._ampm = "AM"

        # Default: tomorrow 10:00 AM
        tomorrow = datetime.now() + timedelta(days=1)
        self.date_var.set(tomorrow.strftime("%m/%d/%Y"))

    def _open_calendar(self):
        if self._cal_window and self._cal_window.winfo_exists():
            self._cal_window.focus()
            return

        self._cal_window = tk.Toplevel(self)
        self._cal_window.title("Select Date")
        self._cal_window.geometry("300x260")
        self._cal_window.resizable(False, False)
        self._cal_window.attributes("-topmost", True)

        try:
            current = datetime.strptime(self.date_var.get(), "%m/%d/%Y")
        except ValueError:
            current = datetime.now() + timedelta(days=1)

        cal = Calendar(self._cal_window, selectmode="day",
                       year=current.year, month=current.month, day=current.day,
                       date_pattern="mm/dd/yyyy",
                       mindate=datetime.now().date(),
                       background="gray20", foreground="white",
                       selectbackground="#2563eb", selectforeground="white")
        cal.pack(fill="both", expand=True, padx=5, pady=5)

        def on_select():
            self.date_var.set(cal.get_date())
            self._cal_window.destroy()
            self._cal_window = None

        tk.Button(self._cal_window, text="Select", command=on_select,
                  bg="#2563eb", fg="white", font=("Arial", 10)).pack(pady=5)

    def _open_time_picker(self):
        if self._time_window and self._time_window.winfo_exists():
            self._time_window.focus()
            return

        def on_time_select(h, m, ampm):
            self._hour = h
            self._minute = m
            self._ampm = ampm
            self.time_var.set(f"{h}:{m:02d} {ampm}")
            self._time_window = None

        self._time_window = TimePicker(self, self._hour, self._minute, self._ampm, on_time_select)

    def get_datetime(self) -> datetime | None:
        date_str = self.date_var.get().strip()
        time_str = self.time_var.get().strip()
        if not date_str or not time_str:
            return None
        try:
            return datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %I:%M %p")
        except ValueError:
            return None

    def set_datetime(self, dt: datetime):
        self.date_var.set(dt.strftime("%m/%d/%Y"))
        self._hour = int(dt.strftime("%I"))
        self._minute = dt.minute
        self._ampm = dt.strftime("%p")
        self.time_var.set(f"{self._hour}:{self._minute:02d} {self._ampm}")

    def set_date_only(self, date_str: str):
        self.date_var.set(date_str)

    def set_time_only(self, hour: int, minute: int, ampm: str = "AM"):
        self._hour = hour
        self._minute = minute
        self._ampm = ampm
        self.time_var.set(f"{hour}:{minute:02d} {ampm}")
