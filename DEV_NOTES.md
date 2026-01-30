# Video Downloader - Development Notes

## Current State (2026-01-30)
Multi-platform video downloader supporting Vimeo, YouTube, Kinescope, GetCourse, and direct m3u8 streams. Batch mode implemented. GUI planned.

## Supported Platforms

| Platform | URL Pattern | Notes |
|----------|-------------|-------|
| Vimeo | `vimeo.com/ID`, `player.vimeo.com/video/ID` | Password, login-required support |
| YouTube | `youtube.com/watch?v=ID`, `youtu.be/ID`, `/shorts/`, `/embed/` | Audio+video auto-merged |
| Kinescope | `kinescope.io/ID/media.m3u8` | Warns if `type=video` (no audio) |
| GetCourse | `gceuproxy.com/api/playlist/master/...` | Russian e-learning platform |
| Direct | Any `.m3u8` URL | Vimeo CDN, etc. |

## Completed Features
- [x] Multi-platform URL detection (Vimeo, YouTube, Kinescope, GetCourse, direct m3u8)
- [x] **Batch mode** - download from file with `--batch urls.txt`
- [x] Video-only stream detection with warnings (Kinescope `type=video`, Vimeo `st=video`)
- [x] Password-protected video support (`--password`)
- [x] Browser cookie extraction (Chrome/Firefox/Edge)
- [x] `--no-cookies` flag for direct URLs
- [x] Custom output filename (`--name` / `-n`)
- [x] Fast mode with 32 concurrent fragments (`--fast` / `-f`)
- [x] aria2c support (`--aria2`)
- [x] Dry-run mode (`--dry-run`)
- [x] List formats (`--list-formats` / `-F`)
- [x] Rich progress bar with fragment progress and percentage fallback
- [x] Temp files in `.downloading/` subfolder
- [x] Uses `python -m yt_dlp` to avoid PATH issues

## Pending Features
- [ ] GUI with interactive queue management
- [ ] Auto-fetch master playlist from video-only URL
- [ ] Manual video+audio URL merging (`--video-url` + `--audio-url`)

## CLI Options
```
Usage: python vimeo_dl.py [OPTIONS] [URL]

Options:
  -B, --batch TEXT        Batch file with URLs (one per line)
  -p, --password TEXT     Password for password-protected videos
  -o, --output TEXT       Output directory (default: current)
  -n, --name TEXT         Output filename (without extension)
  -b, --browser TEXT      Browser for cookies (chrome/firefox/edge)
  --profile TEXT          Browser profile name
  --aria2                 Use aria2c for faster downloads
  -f, --fast              Use 32 concurrent fragments
  --dry-run               Show command without executing
  -F, --list-formats      List available formats
  --no-cookies            Skip cookie extraction
  --no-progress           Disable rich progress bar
```

## File Structure
```
video-downloader/
├── vimeo_dl.py          # CLI entry point (single + batch mode)
├── core/
│   ├── __init__.py
│   ├── detector.py      # URL parsing, platform detection, video-only check
│   ├── downloader.py    # Download orchestration, progress parsing
│   ├── commands.py      # yt-dlp command building, temp folder
│   └── auth.py          # Cookie extraction
├── CLAUDE.md            # AI assistant instructions
├── DEV_NOTES.md         # This file
└── README.md            # User documentation
```

## Code Changes Log

### Session 2026-01-30 (continued)
1. Added YouTube support with URL patterns for watch, youtu.be, embed, shorts
2. Added GetCourse support (`gceuproxy.com/api/playlist/master/...`)
3. Added batch mode with `--batch` flag - downloads from text file
4. Improved progress bar - added fragment progress pattern, simple percentage fallback
5. Temp/part files now go to `.downloading/` subfolder
6. Fixed Kinescope video-only detection (`type=video` in URL)
7. Changed from ffmpeg to native downloader for HLS (better progress output)
8. Updated title from "Vimeo Video Downloader" to "Video Downloader"

### Session 2026-01-30
1. Added Kinescope support with URL pattern `kinescope\.io/[a-f0-9-]+/media\.m3u8`
2. Added `VideoSource` enum to track source platform (VIMEO, KINESCOPE, DIRECT_STREAM)
3. Refactored `CommandBuilder` to use `is_direct_stream()` instead of checking `video_id == "direct_m3u8"`
4. Added rich Progress bar with speed, ETA, and percentage display
5. Added `ProgressParser` class to parse yt-dlp output
6. Added `--no-progress` flag to use yt-dlp native output instead

### Session 2026-01-29
1. Added `skip_cookies` parameter to VimeoDownloader
2. Added CDN m3u8 URL pattern detection
3. Fixed Python module invocation (`sys.executable -m yt_dlp`)
4. Added `--no-cookies-from-browser` to prevent yt-dlp auto-extraction
5. Added `--fast` flag (32 concurrent fragments)
6. Added `--name` for custom output filenames
7. Added `--list-formats` / `-F` flag
8. **DISCOVERED**: Must use Master playlist URL, not video component URL
9. Added master playlist checker with warning for video-only URLs

## Quick Start Commands
```powershell
# Setup ffmpeg PATH (run each session on Windows)
$env:PATH += ";C:\ffmpeg\ffmpeg-8.0.1-essentials_build\bin"

# Clear cache after code changes
Remove-Item -Recurse -Force ".\core\__pycache__" -ErrorAction SilentlyContinue

# Single download
python vimeo_dl.py "https://youtube.com/watch?v=abc123" --no-cookies

# Batch download
python vimeo_dl.py --batch urls.txt --no-cookies --fast

# Dry run to see command
python vimeo_dl.py "https://vimeo.com/123456" --dry-run
```

## Batch File Format
```
# My video queue (comments start with #)
https://youtube.com/watch?v=abc123
https://vimeo.com/123456789

# Empty lines are ignored
https://kinescope.io/abc.../media.m3u8?...
```

## AUDIO ISSUE REFERENCE

### Root Cause
Vimeo/Kinescope CDN separates streams:
- **Master URL** → contains BOTH video and audio
- **Video component** (`type=video` or `st=video`) → video ONLY

### Solution
Tool now detects and warns about video-only URLs. User must use master playlist URL.

### How to Identify
| URL Type | Pattern | Has Audio? |
|----------|---------|------------|
| Master | `/primary/` + `playlist.m3u8` (Vimeo) | Yes |
| Master | `/master/` in path (GetCourse) | Yes |
| Video-only | `type=video` (Kinescope) | No |
| Video-only | `st=video` (Vimeo) | No |

## Dependencies
- Python 3.10+
- yt-dlp (`pip install yt-dlp`)
- click, rich, requests (see requirements.txt)
- ffmpeg (for merging audio+video)
- aria2c (optional, for `--aria2` mode)
