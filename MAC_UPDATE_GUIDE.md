# Mac Branch Update Guide

This document describes all changes made to the Windows version on 2026-02-09 that need to be ported to the Mac branch.

## Summary of New Features

1. **Browser-based Video Detection** - Detects videos from authenticated pages (like Skillshare) using Playwright
2. **Dedicated Detection Profile** - Users can stay logged into their main browser while detecting videos
3. **Real-time Video Discovery** - Videos appear in UI as they're found, with lesson-by-lesson scanning
4. **Cloudflare/Skillshare Support** - Full support for Cloudflare Stream videos with JWT tokens
5. **Improved Settings UI** - Cleaner cookie extraction settings
6. **Standalone Build** - PyInstaller build with bundled ffmpeg, yt-dlp, and Chromium

---

## Files Changed/Created

### New Files

#### `core/browser_detect.py`
Complete browser-based video detection system using Playwright.

**Key functions:**
- `get_detection_profile_dir()` - Returns path to dedicated browser profile
- `setup_detection_profile()` - Opens browser for user to log in (one-time setup)
- `reset_detection_profile()` - Clears profile for re-login
- `BrowserDetector` class - Intercepts network requests to find video URLs
- `detect_videos_async()` - Background thread wrapper

**Mac-specific considerations:**
- Profile path uses `~/Library/Application Support/VideoDownloader/detection-profile` on macOS
- Path logic for macOS:
```python
def get_detection_profile_dir() -> Path:
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home()))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.local' / 'share'
    return base / 'VideoDownloader' / 'detection-profile'
```

**Video URL patterns detected:**
```python
VIDEO_PATTERNS = [
    (r'cloudflarestream\.com/[^/]+/manifest/video\.m3u8', 'cloudflare'),
    (r'player\.vimeo\.com/video/\d+', 'vimeo'),
    (r'vimeocdn\.com/.*\.m3u8', 'vimeo'),
    (r'youtube\.com/watch\?v=', 'youtube'),
    (r'googlevideo\.com/.*\.m3u8', 'youtube'),
    (r'kinescope\.io/[^/]+/media\.m3u8', 'kinescope'),
    (r'gceuproxy\.com/api/playlist/master/', 'getcourse'),
    (r'\.m3u8(?:\?|$)', 'generic'),
]
```

#### `gui/widgets/video_detect_dialog.py`
Dialog for browser-based video detection.

**Features:**
- URL input with Detect button
- Setup Profile button for one-time login
- Real-time video list with checkboxes
- Source badges (color-coded by platform)
- Select All / Add to Queue buttons

**Key callbacks:**
- `_on_video_found()` - Adds video to UI immediately when found
- `_on_detection_progress()` - Updates status label
- `_finish_detection()` - Called when scanning complete

#### `build_exe.py` (Windows only)
Build script for creating standalone executable. Mac version would need `build_mac.py`.

---

### Modified Files

#### `core/detector.py`
Added Skillshare/Cloudflare Stream support.

**Changes:**
1. Added `SKILLSHARE` to `VideoSource` enum
2. Added Cloudflare Stream URL pattern:
```python
CLOUDFLARE_STREAM_PATTERN = r'cloudflarestream\.com/(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)/manifest/video\.m3u8'
```
3. JWT token parsing to extract video ID from `sub` claim

#### `core/commands.py`
Added bundled executable support and filename sanitization.

**Changes:**
1. Added helper functions for bundled tools (in `core/runtime.py` on Mac)
2. Updated `build_ytdlp_command()` to:
   - Use bundled yt-dlp if available
   - Add `--ffmpeg-location` if bundled ffmpeg found
   - Add filename sanitization flags:
```python
"--restrict-filenames",
"--replace-in-metadata", "title", r"[\n\r]", " ",
"--replace-in-metadata", "title", r"\s+", " ",
```

#### `gui/app.py`
Added Detect Videos button and handler.

**Changes:**
1. Added "Detect Videos" button in URL row (purple color #6b5b95)
2. Added `_on_detect_videos()` method
3. Added `_on_detected_videos_add()` callback

#### `gui/widgets/settings_panel.py`
Cookie settings UI.

**Changes:**
1. Checkbox: "Use browser cookies"
2. Browser dropdown for selection

#### `gui/widgets/queue_item_widget.py`
Added Cloudflare color.

**Changes:**
```python
PLATFORM_COLORS = {
    # ... existing colors ...
    "CF": "#f6821f",  # Cloudflare orange
}
```

#### `gui/models/queue_item.py`
Added Skillshare platform mapping.

**Changes:**
```python
PLATFORM_DISPLAY = {
    # ... existing mappings ...
    "skillshare": "CF",
}
```

#### `gui/widgets/url_input.py`
Added filename sanitization on input.

**Changes:**
```python
if filename:
    filename = ' '.join(filename.split())  # Remove newlines, collapse whitespace
```

---

## Key Implementation Details

### Stealth Browser Settings
To avoid bot detection on sites like Skillshare:

```python
context = p.chromium.launch_persistent_context(
    user_data_dir=str(profile_dir),
    headless=False,
    args=[
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-first-run',
        '--no-default-browser-check',
    ],
    ignore_default_args=['--enable-automation'],
    viewport={'width': 1280, 'height': 800},
    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
)

# Inject stealth script
context.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
""")
```

### Lesson Scanning
The detector clicks through lesson lists to capture all videos:

```python
lesson_selectors = [
    '[class*="session-item"] [class*="title"]',
    '[class*="session-item"] a',
    '[class*="lesson-item"] a',
    # ... more selectors
]
```

### Cloudflare Challenge Handling
Waits for "Just a moment" pages to complete:

```python
for i in range(60):
    title = page.title().lower()
    if "just a moment" in title or "checking" in title:
        page.wait_for_timeout(1000)
    else:
        break
```

---

## Mac-Specific Adaptations Needed

### 1. Browser Profile Paths
Update `get_detection_profile_dir()` for macOS:
```python
elif sys.platform == 'darwin':
    base = Path.home() / 'Library' / 'Application Support'
```

### 2. User Agent String
Use Mac user agent in stealth settings:
```python
user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
```

### 3. Build Script
Create `build_mac.py` with:
- Mac ffmpeg download URL
- Mac yt-dlp binary
- Handle Chromium.app bundle structure
- Create .app bundle instead of .exe
- Optional: code signing and notarization

---

## Testing Checklist

- [ ] Video detection dialog opens
- [ ] Setup Profile launches browser correctly
- [ ] Can log into Skillshare in setup browser
- [ ] Browser stays open until manually closed
- [ ] Detection finds videos on class pages
- [ ] Lesson scanning works (clicks through lessons)
- [ ] Videos appear in real-time in dialog
- [ ] Selected videos add to queue correctly
- [ ] Downloads work with detected URLs
- [ ] Cookie extraction setting works

---

## Dependencies

Ensure these are in requirements.txt:
```
playwright>=1.40.0
```

After install, run:
```bash
playwright install chromium
```
