# Rumble Uploader

A Windows desktop app that batch uploads video files from your computer to Rumble with titles, descriptions, tags, categories, thumbnails, and scheduling.

> **Version 2 is a different app from v1.0.0.** Earlier versions downloaded videos from YouTube and re-uploaded them. That has been removed entirely: the app now only uploads video files you already have on your computer, through Rumble Studio. See [What's New](#whats-new-in-version-2).

---

## Features

- **Batch Uploads** - Add as many video files as you like and upload them all in one session
- **Editable Metadata** - Select any video to edit its title, description, and tags before uploading
- **Thumbnails** - Attach a JPG or PNG thumbnail to any video
- **Auto Scheduling** - Set a start date/time and interval, and the app assigns schedule dates to all videos automatically
- **Manual Scheduling** - Override individual video schedule dates with the built-in date/time picker (AM/PM, in your computer's time zone)
- **Queue Persistence** - Your video queue auto-saves every 10 seconds and survives app restarts
- **Progress Tracking** - A progress bar shows the status of the current upload
- **Category per Video** - Pick any of Rumble's primary categories for each video (defaults to News)
- **Rumble Studio** - Uploads go through the current Rumble Studio upload flow
- **Your files stay put** - The app never moves or deletes your videos or thumbnails

---

## Requirements

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10 or Windows 11 |
| **Browser** | Google Chrome (any recent version) |
| **Account** | A Rumble account |
| **Python** | Only to run from source: Python 3.12 or newer |

---

## Installation

1. Download `RumbleUploader-v2.0.0.zip` from the [latest release](https://github.com/djkenada/Rumble-Upload/releases/latest)
2. Extract it to any folder (e.g. `C:\RumbleUploader`)
3. Double-click `RumbleUploader.exe`

No Python is needed. A console window opens alongside the app and shows detailed upload messages. The queue is saved as `queue_data.json` next to the exe.

The **v1.0.0** release is the old YouTube-based version and does not include any of the features described here.

### Running from source

```bash
git clone https://github.com/djkenada/Rumble-Upload.git
cd Rumble-Upload
pip install -r requirements.txt
python main.py
```

### Building the exe

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --console --name RumbleUploader --collect-all customtkinter --collect-all tkcalendar --collect-all selenium --collect-submodules webdriver_manager --hidden-import babel.numbers main.py
```

The exe is written to `dist/`.

---

## Quick Start

### 1. Open the Browser
Click **"Open Browser"** in the app. This opens a dedicated Chrome window on Rumble Studio (studio.rumble.com) that the app controls for uploads.

### 2. Log In
In that Chrome window, log in to your Rumble account until you see the Studio dashboard. The login is remembered in a separate Chrome profile, so you normally only do this once.

### 3. Add Videos
Click **"Add Video Files"** and pick one or more videos. Each one appears in the queue as READY, with the file name as its title.

### 4. Review & Edit
Click a video in the queue to edit it on the right:
- Edit the title, description, and tags, pick a category, then click **"Save Changes"**
- Rumble Studio limits titles to 100 characters and requires a description; if you leave the description empty, the title is used
- Up to 10 tags are sent, separated by commas
- Categories: Automotive, Cooking, Entertainment, Finance & Crypto, Gaming, Health & Science, HowTo, Music, News, Podcasts, Sports, Technology, Travel, Viral, Vlogs
- Click **"Attach Thumbnail"** to pick a JPG or PNG (applies immediately), or **"Remove"** to clear it

### 5. Schedule (optional)
Use the schedule panel to assign publish times:
- Set a **start date** and **start time** (AM/PM format) and an **interval**
- Click **"Auto-Schedule"** to assign times to every video that is ready
- Or select one video and click **"Set Selected"** to give it its own time

Videos without a schedule date are published right away. Rumble Studio schedules in 5-minute steps, so times are rounded to the nearest 5 minutes, and it uses the time zone of the computer running the app.

### 6. Upload
Click **"Upload All"**. The app uploads each ready video in turn, waiting for Rumble to finish receiving each file before it moves on to the visibility step and clicks Finish. Videos that failed earlier are retried. **"Stop"** lets the current upload finish and starts no more.

---

## How It Works

```
Video file on disk
      │
      ├── Title, description, tags, category (edited in the app)
      ├── Thumbnail (optional)
      └── Schedule date/time (optional)
      v
Rumble Studio "Upload video"
      ├── Step 1: file, title, description, category, tags, thumbnail
      ├── waits for the file upload and Rumble's checks to finish
      ├── Step 2: Public or Scheduled, terms checkboxes
      └── Finish
```

The upload is automated via Selenium, controlling the Chrome window you logged into. Videos are posted to your user account (Studio's default author), with Studio's default monetization setting.

---

## Troubleshooting

### "Could not connect to Chrome"
Click **"Open Browser"** first. The app can only control the Chrome window it opened itself.

### "Not logged into Rumble Studio"
Log in at studio.rumble.com in the Chrome window the app opened, then click **"Upload All"** again.

### Rumble upload not working
- **Do not click or interact with the Chrome window** while uploads are in progress
- The app needs full control of the browser to fill forms and click buttons
- The log at the bottom of the app shows what Rumble Studio reported; the console window has more detail on lines starting with `[Rumble]`

### "File upload stalled"
Rumble's upload percentage did not move for 15 minutes, so the app gave up on that video. Check your connection and click **"Upload All"** again to retry it.

### "Rumble won't schedule on ..."
The schedule date or time is in the past. Pick a later time and click **"Upload All"** again.

### A scheduled time is a few minutes off
Rumble Studio only offers times in 5-minute steps, so the app rounds to the nearest one.

### A video shows ERROR with "File not found"
The file was moved, renamed, or deleted after it was added. Remove it from the queue and add it again from its new location.

### App lost my queue
The queue auto-saves to `queue_data.json` next to the app. Your video files are never touched, so you can always add them again.

---

## What's New in Version 2

- **Local files only** - The YouTube download path (yt-dlp, cookies, URL box, title cleanup) is gone. You add video files from your computer.
- **Rumble Studio** - Uploads use Studio's "Upload video" flow instead of the legacy upload page.
- **Waits for the file** - The app watches Rumble's upload percentage and only continues once the file and Rumble's checks are complete.
- **Category per video** - Previously every video was filed under News.
- **Custom thumbnails** - Attach or remove a thumbnail per video.
- **Retry** - "Upload All" retries videos that failed earlier.
- **Nothing is deleted** - Videos and thumbnails are never removed from your disk.
- **Old queues** - A `queue_data.json` from v1 still loads; entries that never had a downloaded file are dropped.

---

## Project Layout

```
main.py                         # Entry point
requirements.txt
app/
  gui.py                        # Main window, queue handling, upload loop
  models/video_metadata.py      # One queued video
  services/rumble_service.py    # Rumble Studio automation (Selenium)
  services/data_store.py        # Saves/loads queue_data.json
  utils/config.py               # Studio URL, category list, Chrome profile path
  widgets/                      # Queue list, editor, schedule panel, progress bar
```

Dependencies: customtkinter, tkcalendar, Pillow, selenium, webdriver-manager.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| GUI | CustomTkinter (modern Tkinter) |
| Rumble Upload | Selenium WebDriver (Chrome) |

---

## License

This project is provided as-is for personal use. Please respect Rumble's terms of service when using this tool. Only upload content you have the rights to distribute.

---

## Contributing

Issues and pull requests are welcome at [github.com/djkenada/Rumble-Upload](https://github.com/djkenada/Rumble-Upload).
