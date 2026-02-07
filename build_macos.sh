#!/usr/bin/env bash
set -euo pipefail

# Build Video Downloader.app for macOS
# Usage: ./build_macos.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/venv"
BUILD_TOOLS="$SCRIPT_DIR/build_tools"
APP="$SCRIPT_DIR/dist/Video Downloader.app"
FRAMEWORKS="$APP/Contents/Frameworks"

echo "==> Checking venv..."
if [ ! -f "$VENV/bin/python3" ]; then
    echo "ERROR: venv not found. Create it first: python3 -m venv venv && pip install -r requirements.txt pyinstaller"
    exit 1
fi

# -----------------------------------------------------------------------
# 1. Download standalone yt-dlp binary (if not cached)
# -----------------------------------------------------------------------
mkdir -p "$BUILD_TOOLS"

YTDLP_BIN="$BUILD_TOOLS/yt-dlp"
if [ -f "$YTDLP_BIN" ]; then
    echo "==> yt-dlp binary already present, skipping download"
else
    echo "==> Downloading standalone yt-dlp binary..."
    YTDLP_URL="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
    curl -L -o "$YTDLP_BIN" "$YTDLP_URL"
    chmod +x "$YTDLP_BIN"
    echo "    Downloaded: $("$YTDLP_BIN" --version 2>/dev/null || echo 'unknown version')"
fi

# -----------------------------------------------------------------------
# 2. Verify ffmpeg / ffprobe are available
# -----------------------------------------------------------------------
echo "==> Checking for ffmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    echo "ERROR: ffmpeg not found. Install it: brew install ffmpeg"
    exit 1
fi
echo "    ffmpeg:  $(which ffmpeg) -> $(readlink -f "$(which ffmpeg)" 2>/dev/null || which ffmpeg)"
echo "    ffprobe: $(which ffprobe) -> $(readlink -f "$(which ffprobe)" 2>/dev/null || which ffprobe)"

# -----------------------------------------------------------------------
# 3. Build .app with PyInstaller (bundles ffmpeg/ffprobe + dylibs)
# -----------------------------------------------------------------------
echo "==> Building Video Downloader.app..."
"$VENV/bin/pyinstaller" video_dl_gui.spec --noconfirm

# -----------------------------------------------------------------------
# 4. Copy yt-dlp into the bundle AFTER PyInstaller
#    (yt-dlp_macos is itself a PyInstaller binary — if included during
#    the build, PyInstaller's signing/stripping mangles it)
# -----------------------------------------------------------------------
echo "==> Injecting yt-dlp binary into .app bundle..."
cp "$YTDLP_BIN" "$FRAMEWORKS/yt-dlp"
chmod +x "$FRAMEWORKS/yt-dlp"

# Re-sign the bundle after adding yt-dlp
echo "==> Re-signing .app bundle..."
codesign --force --deep --sign - "$APP" 2>/dev/null || true

echo ""
echo "==> Build complete!"
echo "    Output: dist/Video Downloader.app"
du -sh "$APP" | awk '{print "    Size:   " $1}'
echo ""
echo "    To run:  open \"dist/Video Downloader.app\""
