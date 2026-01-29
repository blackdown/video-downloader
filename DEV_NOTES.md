# Video Downloader - Development Notes

## Current State (2026-01-29)
CLI tool for downloading Vimeo videos using yt-dlp. Working with audio!

## AUDIO ISSUE: SOLVED ✓

### Root Cause
Vimeo CDN separates streams:
- **Master URL** (`playlist.m3u8`) → contains BOTH video and audio
- **Video component** (`media.m3u8?st=video`) → video ONLY
- **Audio component** (`media.m3u8?st=audio`) → audio ONLY

### Solution
Always use the **Master URL**. Tool now warns if video-only URL detected.

### How to Identify URLs
| URL Type | Pattern | Has Audio? |
|----------|---------|------------|
| Master | `/primary/` + `playlist.m3u8` | ✓ Yes |
| Video-only | `media.m3u8` + `st=video` | ✗ No |
| Audio-only | `media.m3u8` + `st=audio` | Audio only |

## Completed Features
- [x] Basic Vimeo URL detection (`vimeo.com/123456`, `player.vimeo.com/video/123456`)
- [x] Password-protected video support (`--password`)
- [x] Browser cookie extraction (Chrome/Firefox/Edge)
- [x] `--no-cookies` flag for direct URLs
- [x] Direct m3u8 CDN URL support (`vimeocdn.com/*.m3u8`)
- [x] Custom output filename (`--name` / `-n`)
- [x] Timestamp-based naming for direct m3u8 downloads
- [x] Fast mode with 32 concurrent fragments (`--fast` / `-f`)
- [x] aria2c support (`--aria2`)
- [x] Dry-run mode (`--dry-run`)
- [x] List formats (`--list-formats` / `-F`)
- [x] Uses `python -m yt_dlp` to avoid PATH issues
- [x] ffmpeg downloader for m3u8 streams
- [x] **Master playlist checker with warning**
- [x] **Clean progress output** (suppressed ffmpeg HTTP noise)

## ffmpeg Installation
Path: `C:\ffmpeg\ffmpeg-8.0.1-essentials_build\bin`

Add to PATH each session:
```powershell
$env:PATH += ";C:\ffmpeg\ffmpeg-8.0.1-essentials_build\bin"
```

## CLI Options
```
Usage: python vimeo_dl.py [OPTIONS] URL

Options:
  -p, --password TEXT   Password for password-protected videos
  -o, --output TEXT     Output directory (default: current)
  -n, --name TEXT       Output filename (without extension)
  -b, --browser TEXT    Browser for cookies (chrome/firefox/edge)
  --profile TEXT        Browser profile name
  --aria2               Use aria2c for faster downloads
  -f, --fast            Use 32 concurrent fragments
  --dry-run             Show command without executing
  -F, --list-formats    List available formats
  --no-cookies          Skip cookie extraction
```

## File Structure
```
video-downloader/
├── vimeo_dl.py          # CLI entry point
├── core/
│   ├── __init__.py
│   ├── detector.py      # URL parsing, type detection, master playlist check
│   ├── downloader.py    # Download orchestration, warnings
│   ├── commands.py      # yt-dlp command building
│   └── auth.py          # Cookie extraction
└── DEV_NOTES.md
```

## Pending Features

### Kinescope Support
- URL pattern: `kinescope.io/{id}/media.m3u8?quality=...&type=video&sign=...&expires=...`
- Add to detector.py:
  ```python
  KINESCOPE_URL_PATTERN = r'kinescope\.io/[a-f0-9-]+/media\.m3u8'
  ```

### Other Ideas
- Auto-detect and fetch master playlist from video-only URL
- `--video-url` + `--audio-url` option for manual merging
- Progress bar using rich library instead of yt-dlp native

## Code Changes Log

### Session 2026-01-29
1. Added `skip_cookies` parameter to VimeoDownloader
2. Added CDN m3u8 URL pattern detection
3. Fixed Python module invocation (`sys.executable -m yt_dlp`)
4. Added `--no-cookies-from-browser` to prevent yt-dlp auto-extraction
5. Added `--fast` flag (32 concurrent fragments)
6. Added `--name` for custom output filenames
7. Added `--list-formats` / `-F` flag
8. Switched to ffmpeg downloader for m3u8 streams
9. **DISCOVERED**: Must use Master playlist URL, not video component URL
10. **CONFIRMED**: Master URL downloads with audio working!
11. Added clean progress output (ffmpeg `-loglevel warning`)
12. Added master playlist checker with warning for video-only URLs

## Quick Start Commands
```powershell
# Setup ffmpeg PATH (run each session)
$env:PATH += ";C:\ffmpeg\ffmpeg-8.0.1-essentials_build\bin"

# Clear cache after code changes
Remove-Item -Recurse -Force ".\core\__pycache__" -ErrorAction SilentlyContinue

# Download with master URL
$url = "https://vod-adaptive-ak.vimeocdn.com/.../primary/.../playlist.m3u8?..."
python vimeo_dl.py $url --no-cookies -n "video_name"

# Test video-only warning
$badurl = "https://vod-adaptive-ak.vimeocdn.com/.../media.m3u8?...&st=video"
python vimeo_dl.py $badurl --no-cookies --dry-run
```

## Dependencies
- Python 3.13+
- yt-dlp (`pip install yt-dlp`)
- click (`pip install click`)
- rich (`pip install rich`)
- requests
- ffmpeg 8.0.1 (C:\ffmpeg\...)
