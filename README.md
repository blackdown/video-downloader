# Video Downloader

Multi-platform video downloader with a GUI, automatic platform detection, browser-based video scanning, and authenticated site support.

## Supported Platforms

| Platform | Notes |
|----------|-------|
| **YouTube** | Public videos |
| **Vimeo** | Public, unlisted, password-protected, embed-only |
| **Kinescope** | HLS master playlists |
| **GetCourse** | HLS proxy streams |
| **Skillshare** | Cloudflare Stream (requires login profile) |
| **Patreon / Mux** | `stream.mux.com` — use Source page URL field |
| **Direct HLS** | Any `.m3u8` stream URL |

## GUI Usage

Run the GUI:

```bash
python main.py
```

Or use the bundled `video_dl.exe` on Windows.

### Adding a URL

Paste a video URL into the URL field and click **+ Add** (or press Enter).

For direct stream URLs from sites like Patreon that restrict playback by origin, also paste the page you found the video on into the **Source page URL** field — this is sent as the HTTP `Referer` header.

### Authenticated Sites (Skillshare, Patreon, etc.)

1. Go to **Settings** and click **Setup Profile** under the Login Profile section.
2. A Chrome window opens — log in to any sites you want to download from.
3. Close the browser when done.
4. Downloads will now use the saved session cookies automatically.

The profile is stored at `%LOCALAPPDATA%\VideoDownloader\detection-profile` and persists between sessions.

### Detect Videos from a Page

Click **Detect Videos** to open the browser scanner:

1. Enter a page URL (e.g., a Skillshare class page).
2. Click **Detect** — Chrome opens and scans network requests for video streams.
3. Check the videos found and click **Add to Queue**.

This works for any site where the video URL isn't visible in the page source.

### Queue Controls

| Button | Action |
|--------|--------|
| **Start** | Start/resume downloading |
| **Pause** | Stop starting new downloads (current download finishes) |
| **Cancel** | Cancel all active downloads |
| **Clear Done** | Remove completed/error/cancelled items |
| **Open Folder** | Open the output folder in Explorer |

### Batch Files

Click **Batch File** to load a `.txt` file with one URL per line. Lines starting with `#` are ignored.

---

## CLI Usage

```bash
python video_dl.py "URL" [OPTIONS]
```

### Options

```
  -B, --batch TEXT       Batch file with URLs (one per line)
  -p, --password TEXT    Password for password-protected Vimeo videos
  -o, --output TEXT      Output directory (default: current directory)
  -n, --name TEXT        Output filename (without extension)
  -b, --browser TEXT     Browser for cookies (chrome/firefox/edge)
  --profile TEXT         Browser profile name (e.g. "Profile 1")
  --aria2                Use aria2c for faster downloads
  -f, --fast             32 concurrent fragments instead of 16
  --dry-run              Print command without running it
  -F, --list-formats     List available formats
  --no-cookies           Skip cookie extraction
  --no-progress          Disable rich progress bar
```

---

## Installation

### Windows: Standalone Executable

Download `video_dl.exe` from the [Releases](../../releases) page.

Install external tools:
```powershell
winget install yt-dlp
winget install ffmpeg
```

### Run from Source

1. Install external tools (see above or use your package manager).

2. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux

pip install -r requirements.txt
playwright install chromium
```

3. Run:
```bash
python main.py        # GUI
python video_dl.py    # CLI
```

---

## Troubleshooting

### 403 Forbidden on Mux/Patreon streams
The stream URL has an origin restriction. Paste the Patreon post URL into the **Source page URL** field — this sends it as the HTTP `Referer`.

### No audio in downloaded video
You have a video-only stream URL. You need the master playlist URL (usually contains `/primary/` and ends with `playlist.m3u8`).

### Site not logging in through Setup Profile
Some sites detect automation. Close the profile browser fully between sessions. The Setup Profile button opens a plain Chrome window (no automation flags).

### "Could not extract cookies" / authentication failures
Set up the login profile via Settings → Setup Profile. Downloads will use the saved session instead of live browser cookies.

### URL expired or instant 403
Direct stream URLs expire. Get a fresh URL from the source page.

---

## Project Structure

```
video-downloader/
├── main.py              # GUI entry point
├── video_dl.py          # CLI entry point
├── core/
│   ├── detector.py      # URL and platform detection
│   ├── downloader.py    # Download orchestration
│   ├── commands.py      # yt-dlp command building
│   ├── auth.py          # Cookie extraction and decryption
│   └── browser_detect.py # Playwright-based video detection
├── gui/
│   ├── app.py           # Main window
│   ├── managers/        # Queue, workers, events
│   ├── models/          # Settings, queue item dataclasses
│   └── widgets/         # UI components
└── requirements.txt
```

## License

MIT License
