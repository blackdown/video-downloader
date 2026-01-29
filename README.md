# Vimeo Video Downloader

Intelligent Vimeo video downloader with automatic type detection and authentication handling.

## Features

- Automatic video type detection (public, password-protected, login-required, embed-only, direct streams)
- Direct m3u8/HLS stream URL support - paste CDN URLs directly
- **Master playlist detection** - warns if you're using a video-only URL
- Browser cookie extraction (Chrome, Firefox, Edge)
- Password-protected video support
- Parallel fragment downloads (16 or 32 in fast mode)
- Optional aria2c integration for maximum speed
- Custom output filenames
- Clean progress output
- Clean MP4 output with proper metadata

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install external tools

**Windows:**
```powershell
# Install yt-dlp
pip install yt-dlp

# Install ffmpeg (required for audio/video merging)
winget install ffmpeg
# OR download manually from https://www.gyan.dev/ffmpeg/builds/
# Extract to C:\ffmpeg and add bin folder to PATH:
$env:PATH += ";C:\ffmpeg\ffmpeg-8.0.1-essentials_build\bin"
```

**macOS (Homebrew):**
```bash
brew install yt-dlp ffmpeg
# Optional: for maximum speed
brew install aria2
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install yt-dlp ffmpeg
# Optional: for maximum speed
sudo apt install aria2
```

## Usage

### Basic Examples

**Download a public video:**
```bash
python vimeo_dl.py https://vimeo.com/123456789
```

**Password-protected video:**
```bash
python vimeo_dl.py https://vimeo.com/123456789/hash --password mypassword
```

**Direct stream URL with custom filename:**
```bash
python vimeo_dl.py "https://vod-adaptive-ak.vimeocdn.com/.../playlist.m3u8?..." --no-cookies -n "My Video"
```

**Fast download (32 concurrent fragments):**
```bash
python vimeo_dl.py "https://..." --no-cookies --fast
```

**List available formats:**
```bash
python vimeo_dl.py "https://..." --no-cookies -F
```

**Use aria2 for faster downloads:**
```bash
python vimeo_dl.py https://vimeo.com/123456789 --aria2
```

**Dry run (show command without executing):**
```bash
python vimeo_dl.py https://vimeo.com/123456789 --dry-run
```

### All Options

```
Usage: vimeo_dl.py [OPTIONS] URL

Options:
  -p, --password TEXT  Password for password-protected videos
  -o, --output TEXT    Output directory (default: current directory)
  -n, --name TEXT      Output filename (without extension)
  -b, --browser TEXT   Browser to extract cookies from (chrome/firefox/edge)
  --profile TEXT       Browser profile name (e.g., "Profile 1", "Default")
  --aria2              Use aria2c for faster downloads
  -f, --fast           Fast mode - 32 concurrent fragment downloads
  --dry-run            Show command without executing
  -F, --list-formats   List available formats without downloading
  --no-cookies         Skip cookie extraction (for direct URLs)
  --help               Show this message and exit
```

## Important: Master Playlist vs Video-Only URLs

When downloading direct m3u8 streams, you MUST use the **Master playlist URL**, not a video-only component URL.

| URL Type | Pattern | Audio? |
|----------|---------|--------|
| Master (use this!) | Contains `/primary/` and `playlist.m3u8` | Yes |
| Video-only | Contains `media.m3u8` and `st=video` | **NO** |
| Audio-only | Contains `media.m3u8` and `st=audio` | Audio only |

The tool will warn you if it detects a video-only URL:
```
WARNING: This appears to be a video-only stream URL!
  Audio may be missing. Use the Master playlist URL instead.
```

**How to find the Master URL:**
1. Open DevTools (F12) → Network tab
2. Filter by "m3u8"
3. Look for URLs containing `/primary/` and ending in `playlist.m3u8`
4. Avoid URLs ending in `media.m3u8` with `st=video`

## How It Works

1. **URL Analysis**: Extracts video ID and hash from the Vimeo URL, or detects direct m3u8 stream URLs
2. **Type Detection**: Determines video type and checks for master playlist
3. **Authentication**: Automatically extracts cookies from your browser (not needed for direct streams)
4. **Download**: Uses yt-dlp with ffmpeg for optimal quality
5. **Post-processing**: Merges audio/video and outputs clean MP4

## Troubleshooting

### No audio in downloaded video
You're using a **video-only** stream URL. Use the **Master playlist** URL instead. See the section above.

### "Could not extract cookies: This operation requires admin"
On Windows, use `--no-cookies` for direct m3u8 URLs:
```bash
python vimeo_dl.py "YOUR_M3U8_URL" --no-cookies
```

### "yt-dlp not found"
```bash
pip install yt-dlp
```

### ffmpeg not found / MPEG-TS warnings
Install ffmpeg and add to PATH:
```powershell
# Windows - download from https://www.gyan.dev/ffmpeg/builds/
# Extract and add to PATH:
$env:PATH += ";C:\ffmpeg\ffmpeg-8.0.1-essentials_build\bin"
```

### "URL expired" or "403 Forbidden"
Direct stream URLs expire (usually in a few hours). Get a fresh URL from DevTools.

### Lots of HTTP request spam in output
Update to the latest version - verbose ffmpeg output has been suppressed.

## Project Structure

```
vimeo-downloader/
├── vimeo_dl.py          # Main CLI entry point
├── core/
│   ├── __init__.py
│   ├── detector.py      # URL/video type detection + master playlist check
│   ├── downloader.py    # Download orchestration
│   ├── auth.py          # Cookie/auth handling
│   └── commands.py      # Command construction
├── requirements.txt
├── DEV_NOTES.md         # Development notes
└── README.md
```

## Credits

Built with inspiration from Devin Schumacher's comprehensive Vimeo download guide:
https://gist.github.com/devinschumacher/8024bc4693d79aef641b2c281e45d6cb

## License

MIT License - Feel free to use and modify as needed.
