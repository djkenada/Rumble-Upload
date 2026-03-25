import os

# Fix Windows encoding issues with unicode/emoji in YouTube metadata
os.environ["PYTHONUTF8"] = "1"

from app.gui import App


def main():
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
