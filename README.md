# Rumble Uploader

A Windows desktop app that batch downloads YouTube videos and uploads them to Rumble with full metadata, scheduling, and clickbait title cleanup.

---

## Features

- **Batch Processing** - Paste multiple YouTube URLs at once and process them all in a single session
- **Auto Metadata** - Automatically fetches title, description, tags, and thumbnail from YouTube
- **Editable Metadata** - Expand any video to edit its title, description, and tags before uploading
- **Clickbait Title Cleanup** - Automatically removes sensationalized words and phrases that violate Rumble's content guidelines
- **Auto Scheduling** - Set a start date/time and interval, and the app assigns schedule dates to all videos automatically
- **Manual Scheduling** - Override individual video schedule dates with the built-in date/time picker (Central Time, AM/PM)
- **1080p Downloads** - Downloads the best available quality up to 1080p, with automatic video+audio merging
- **Queue Persistence** - Your video queue auto-saves every 10 seconds and survives app restarts
- **Progress Tracking** - Compact progress bars for both download and upload status per video
- **Category Auto-Set** - Automatically sets the Rumble category to News
- **Thumbnail Upload** - Attaches the YouTube thumbnail to the Rumble upload
- **Cookie Management** - One-click YouTube cookie extraction from the browser for authenticated downloads

---

## Requirements

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10 or Windows 11 |
| **Browser** | Google Chrome (any recent version) |
| **Accounts** | A Rumble account and a YouTube account |

**No other software is required.** The release package includes everything: yt-dlp, ffmpeg, ffprobe, and deno are all bundled.

---

## Installation

1. Download `RumbleUploader.zip` from the [latest release](https://github.com/djkenada/Rumble-Upload/releases/latest)
2. Extract the zip to any folder (e.g. `C:\RumbleUploader`)
3. Double-click `RumbleUploader.exe`

That's it. No Python, no pip, no installers.

---

## Quick Start

### 1. Launch Chrome
Click **"Launch Chrome"** in the app. This opens a dedicated Chrome window that the app controls for Rumble uploads.

### 2. Log In
In the Chrome window:
- Navigate to **rumble.com** and log in to your Rumble account
- Navigate to **youtube.com** and log in to your YouTube account

### 3. Get YouTube Cookies
Back in the app, click **"Get YT Cookies"**. This saves your YouTube session so the app can download videos without being blocked.

### 4. Add Videos
Paste one or more YouTube URLs into the text box (one per line or separated by spaces) and click **"Add to Queue"**. The app fetches metadata for each video sequentially to avoid rate limiting.

### 5. Review & Edit
Each video appears in the queue with its thumbnail, title, and status. Click the expand arrow to:
- Edit the title (auto-cleaned of clickbait)
- Edit the description
- Modify tags
- Set a custom schedule date/time

### 6. Schedule
Use the **Schedule Panel** to auto-assign upload times:
- Set a **start date** and **start time** (Central Time, AM/PM format)
- Set the **interval** in minutes between uploads
- Click **"Auto Schedule"** to assign times to all downloaded videos

### 7. Download & Upload
- **"Download All"** - Downloads all queued videos from YouTube at up to 1080p
- **"Download & Upload All"** - Downloads and then uploads each video to Rumble with full metadata, thumbnail, category, and schedule date

---

## How It Works

```
YouTube URL ──> Fetch Metadata ──> Download Video (1080p)
                    │                       │
                    ├── Title (cleaned)      │
                    ├── Description          │
                    ├── Tags                 │
                    └── Thumbnail            │
                                            v
                                    Upload to Rumble
                                        │
                                        ├── Video file
                                        ├── Title & Description
                                        ├── Tags
                                        ├── Thumbnail
                                        ├── Category (News)
                                        └── Schedule date/time
```

The Rumble upload is automated via Selenium, controlling the Chrome window you logged into. The app fills in every field on Rumble's upload form, scrolls to the scheduler, sets the date and time, and submits.

---

## Clickbait Title Cleanup

Rumble has stricter content guidelines than YouTube. The app automatically removes common clickbait patterns:

| Pattern | Example Before | Example After |
|---------|---------------|---------------|
| Sensational openers | "OMG! Breaking News Today" | "Breaking News Today" |
| Reaction phrases | "Democrats Are Stunned" | *(removed or softened)* |
| Excessive punctuation | "This Changes Everything!!!" | "This Changes Everything" |
| Filler words | "Just In: Report Shows..." | "Report Shows..." |

You can always manually edit titles before uploading.

---

## File Structure

```
RumbleUploader/
  ├── RumbleUploader.exe    # Main application
  ├── yt-dlp.exe            # YouTube video downloader
  ├── ffmpeg.exe            # Video/audio merging (1080p)
  ├── ffprobe.exe           # Video analysis
  ├── deno.exe              # JavaScript runtime (YouTube anti-bot)
  ├── README.txt            # Offline instructions
  └── downloads/            # Working folder
       ├── *.mp4            # Downloaded videos
       ├── *_thumb.jpg      # Thumbnails
       ├── cookies.txt      # YouTube session cookies
       └── queue_data.json  # Saved queue state
```

**Important:** Keep all files in the same folder. Do not move or delete individual executables.

---

## Troubleshooting

### "Sign in to confirm you're not a bot"
YouTube detected automated access. Fix:
1. Make sure you're logged into YouTube in the Chrome window
2. Click **"Get YT Cookies"** to refresh your session
3. Wait a minute before retrying if you fetched many videos at once

### "Requested format is not available"
The video may not have 1080p available, or the JS challenge solver failed. The app automatically falls back to lower resolutions. If it persists, refresh cookies.

### Downloads are slow or stalling
YouTube throttles downloads. The app uses deno to solve YouTube's speed challenges. If downloads are extremely slow, try refreshing cookies.

### Rumble upload not working
- Make sure you're logged into Rumble in the Chrome window
- **Do not click or interact with the Chrome window** while uploads are in progress
- The app needs full control of the browser to fill forms and click buttons

### App lost my queue
The queue auto-saves to `downloads/queue_data.json`. If the app crashes before saving, downloaded videos are still in the `downloads/` folder and will be detected on next launch.

---

## Building from Source

If you want to build the exe yourself:

```bash
# Clone the repo
git clone https://github.com/djkenada/Rumble-Upload.git
cd Rumble-Upload

# Install Python 3.12+ and dependencies
pip install -r requirements.txt
pip install pyinstaller

# Run from source
python main.py

# Build the exe
pyinstaller build.spec --clean --noconfirm

# The exe will be in dist/
# Copy yt-dlp.exe, ffmpeg.exe, ffprobe.exe, and deno.exe into dist/
```

### Dependencies (for source builds)
- Python 3.12+
- customtkinter
- Pillow
- selenium
- requests
- yt-dlp

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| GUI | CustomTkinter (modern Tkinter) |
| YouTube Downloads | yt-dlp (standalone exe) |
| Video Processing | FFmpeg |
| Rumble Upload | Selenium WebDriver (Chrome) |
| JS Challenge Solving | Deno runtime |
| Packaging | PyInstaller |

---

## License

This project is provided as-is for personal use. Please respect the terms of service of both YouTube and Rumble when using this tool. Only upload content you have the rights to distribute.

---

## Contributing

Issues and pull requests are welcome at [github.com/djkenada/Rumble-Upload](https://github.com/djkenada/Rumble-Upload).
