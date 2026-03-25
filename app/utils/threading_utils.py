import threading
import traceback
import queue


class ThreadSafeCallback:
    """Thread-safe callback system for updating Tkinter from background threads.

    Tkinter's after() can be unreliable when called from threads on Windows.
    This uses a queue that the main thread polls periodically.
    """

    def __init__(self, root, poll_interval=100):
        self._root = root
        self._queue = queue.Queue()
        self._poll_interval = poll_interval
        self._polling = False

    def start_polling(self):
        if not self._polling:
            self._polling = True
            self._poll()

    def stop_polling(self):
        self._polling = False

    def _poll(self):
        """Process all pending callbacks on the main thread."""
        try:
            while True:
                callback = self._queue.get_nowait()
                try:
                    callback()
                except Exception as e:
                    print(f"[Callback Error] {e}")
        except queue.Empty:
            pass
        if self._polling:
            self._root.after(self._poll_interval, self._poll)

    def schedule(self, callback):
        """Schedule a callback to run on the main thread."""
        self._queue.put(callback)


def run_in_thread(root, func, callback=None, error_callback=None):
    """Run func in a daemon thread. Schedule callback/error_callback on the main thread."""

    def wrapper():
        try:
            result = func()
            if callback:
                root.after(0, lambda r=result: callback(r))
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[Thread Error] {e}\n{tb}")
            if error_callback:
                root.after(0, lambda err=e: error_callback(err))

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread
