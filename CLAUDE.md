# Claude Code Context

## Project Overview

Video downloader with CLI (`video_dl.py`) and GUI (`video_dl_gui.py`) interfaces.
Uses yt-dlp + ffmpeg for downloads, customtkinter for GUI.
macOS `.app` bundle built with PyInstaller via `./build_macos.sh`.

## Architecture

- `core/` - Shared logic (detection, download, commands, auth, runtime)
- `gui/` - GUI app (managers for download workers, logging, queue; widgets for UI)
- `core/runtime.py` - Frozen vs source mode detection; binary path resolution
- `core/downloader.py` - Shared by CLI and GUI; `rich` only imported in non-frozen mode

## Key Design Decisions

### PyInstaller + yt-dlp
The bundled `yt-dlp_macos` is itself a PyInstaller binary. It must be copied into the
`.app` AFTER PyInstaller runs (not as a binary/data input) to avoid mangling. The env
passed to subprocess must have PyInstaller vars (`_MEIPASS2`, `_PYI*`, etc.) stripped
so the child yt-dlp boots cleanly. See `ffmpeg_env()` in `core/runtime.py`.

### rich module
`rich` is used for CLI console output only. In frozen (GUI) mode, `core/downloader.py`
skips importing `rich` entirely and uses a `_NullConsole` stub instead. This avoids
PyInstaller bundling issues with `rich._unicode_data.unicode17-0-0` (hyphenated module
name that PyInstaller can't resolve).

### Paths in frozen mode
When launched from Finder, CWD is `/` (read-only). All file paths must be absolute:
- Logs: `~/Library/Logs/Video Downloader/video_dl_gui.log`
- Settings: `~/Library/Application Support/Video Downloader/settings.json`
- Path logic: `_default_log_path()` in `gui/managers/logger.py`,
  `_default_settings_path()` in `gui/models/settings.py`

### Logging
`sys.stdout` is `None` in frozen `.app` (console=False). Logger guards the
`StreamHandler` behind `if sys.stdout is not None`.

## Build

```bash
./build_macos.sh   # clean build: rm -rf build dist first
```

Requires: venv with deps + pyinstaller, brew-installed ffmpeg, internet for yt-dlp download.

## Known Issues / Future Work

- The `.app` is x86_64 only (built with Homebrew Python on Intel). An ARM build would
  need an ARM venv and Homebrew ffmpeg built for ARM.
- `video_dl_gui.spec` still lists `rich` in hiddenimports (harmless, but unnecessary
  now that rich is conditionally imported).
- No auto-update mechanism for the bundled yt-dlp binary.
