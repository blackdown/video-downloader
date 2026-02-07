# Video Downloader

Multi-platform video downloader with automatic detection, batch downloads, and rich progress display. Available as a CLI tool and a macOS GUI app.

## Supported Platforms

| Platform | URL Examples |
|----------|--------------|
| **YouTube** | `youtube.com/watch?v=ID`, `youtu.be/ID`, `/shorts/`, `/embed/` |
| **Vimeo** | `vimeo.com/ID`, `player.vimeo.com/video/ID` |
| **Kinescope** | `kinescope.io/ID/media.m3u8?...` |
| **GetCourse** | `gceuproxy.com/api/playlist/master/...` |
| **Direct HLS** | Any `.m3u8` stream URL |

## Features

- Automatic platform and video type detection
- **Batch downloads** - queue multiple URLs from a file
- Browser cookie extraction (Chrome, Firefox, Edge)
- Password-protected video support (Vimeo)
- Video-only stream detection with warnings
- Parallel fragment downloads (16 or 32 in fast mode)
- Optional aria2c integration for maximum speed
- Rich progress bar with speed and ETA
- Clean MP4 output with proper metadata

## Installation

### macOS: Standalone App

Build the `.app` bundle (bundles yt-dlp and ffmpeg — no external tools needed):

```bash
# One-time setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt pyinstaller
brew install ffmpeg

# Build
./build_macos.sh
open "dist/Video Downloader.app"
```

The app stores logs in `~/Library/Logs/Video Downloader/` and settings in `~/Library/Application Support/Video Downloader/`.

### Windows: Standalone Executable

Download `video_dl.exe` from the [Releases](../../releases) page. No Python required.

You still need to install the external tools:
```powershell
winget install yt-dlp
winget install ffmpeg
```

### Any Platform: Run from Source

1. Install external tools:

**macOS:**
```bash
brew install yt-dlp ffmpeg python
```

**Linux:**
```bash
sudo apt install yt-dlp ffmpeg python3 python3-pip
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Run the GUI or CLI:
```bash
python video_dl_gui.py                         # GUI
python video_dl.py "https://..." --no-cookies  # CLI
```

## Usage

**macOS App:** Open `Video Downloader.app` — add URLs, set output folder, download.
**Windows:** Use `video_dl.exe`
**CLI:** Use `python video_dl.py`

### Single Video Download

```bash
# YouTube
video_dl.exe "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Vimeo (public)
video_dl.exe https://vimeo.com/123456789

# Vimeo (password-protected)
video_dl.exe https://vimeo.com/123456789 --password mypass

# Direct stream URL
video_dl.exe "https://example.com/video.m3u8" --no-cookies

# Fast mode (32 concurrent fragments)
video_dl.exe "https://..." --fast
```

### Batch Download

Create a text file with URLs (one per line):

**urls.txt:**
```
# My video queue
https://www.youtube.com/watch?v=abc123
https://vimeo.com/123456789

# Comments start with #, empty lines ignored
https://kinescope.io/abc.../media.m3u8?...
```

Download all:
```bash
video_dl.exe --batch urls.txt --no-cookies --fast
```

### All Options

```
Usage: video_dl.exe [OPTIONS] [URL]

Options:
  -B, --batch TEXT       Batch file with URLs (one per line)
  -p, --password TEXT    Password for password-protected videos
  -o, --output TEXT      Output directory (default: current directory)
  -n, --name TEXT        Output filename (without extension)
  -b, --browser TEXT     Browser to extract cookies from (chrome/firefox/edge)
  --profile TEXT         Browser profile name (e.g., "Profile 1", "Default")
  --aria2                Use aria2c for faster downloads
  -f, --fast             Fast mode - 32 concurrent fragment downloads
  --dry-run              Show command without executing
  -F, --list-formats     List available formats without downloading
  --no-cookies           Skip cookie extraction (for direct URLs)
  --no-progress          Disable rich progress bar
  --help                 Show this message and exit
```

## Important: Video-Only Stream URLs

Some platforms (Kinescope, Vimeo CDN) separate video and audio into different streams. The tool will warn you if it detects a video-only URL:

```
WARNING: This is a video-only stream URL (type=video)!
  Audio will be missing. You need the master playlist URL instead.
```

**How to identify URL types:**

| URL Type | Pattern | Audio? |
|----------|---------|--------|
| Master (use this!) | `/master/` or `/primary/` + `playlist.m3u8` | Yes |
| Video-only | `type=video` or `st=video` in URL | **NO** |

**Solution:** Go back to the source and find the master playlist URL, or look for a URL without `type=video`.

## How It Works

1. **URL Analysis**: Detects platform and extracts video ID
2. **Type Detection**: Checks for password protection, video-only streams
3. **Authentication**: Extracts cookies from browser if needed
4. **Download**: Uses yt-dlp with optimal settings for each platform
5. **Post-processing**: Merges audio/video into clean MP4

## Troubleshooting

### No audio in downloaded video
You're using a video-only stream URL. Use the master playlist URL instead. See section above.

### "Could not extract cookies"
Use `--no-cookies` for direct stream URLs:
```bash
video_dl.exe "YOUR_URL" --no-cookies
```

### Progress bar not updating
Try `--no-progress` to see raw yt-dlp output and diagnose issues.

### "URL expired" or "403 Forbidden"
Direct stream URLs expire. Get a fresh URL from the source.

## Building from Source

### macOS .app Bundle

```bash
./build_macos.sh
```

Requires a venv with dependencies + pyinstaller, and Homebrew ffmpeg.
The script downloads a standalone yt-dlp binary, builds with PyInstaller,
injects yt-dlp into the bundle, and re-signs.

### Windows CLI Executable

```bash
pip install pyinstaller
pyinstaller --onefile --name video_dl --console video_dl.py
```

## Project Structure

```
video-downloader/
├── video_dl.py          # CLI entry point
├── video_dl_gui.py      # GUI entry point
├── video_dl_gui.spec    # PyInstaller spec for macOS .app
├── build_macos.sh       # macOS build script
├── core/
│   ├── runtime.py       # Frozen/source mode detection
│   ├── detector.py      # URL/platform detection
│   ├── downloader.py    # Download orchestration
│   ├── commands.py      # yt-dlp command building
│   └── auth.py          # Cookie handling
├── gui/
│   ├── app.py           # Main window
│   ├── managers/        # Download workers, logging, queue
│   ├── models/          # Settings, queue items
│   └── widgets/         # UI components
├── requirements.txt
└── README.md
```

## License

MIT License - Feel free to use and modify as needed.
