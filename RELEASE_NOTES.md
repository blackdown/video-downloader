# Release Notes

## v1.1.0 - macOS App Bundle Fixes

**Bug fixes:**
- Fixed downloads failing in standalone `.app` with `ModuleNotFoundError: rich._unicode_data.unicode17-0-0` - `rich` is now skipped entirely in frozen mode (GUI doesn't need it)
- Fixed bundled yt-dlp crashing due to inherited PyInstaller env vars (`_MEIPASS2`) - subprocess environment is now cleaned before spawning yt-dlp
- Fixed log file not being written - `sys.stdout` is `None` in `.app` bundles, which crashed the logging setup
- Fixed log viewer showing empty - it was reading from `./video_dl_gui.log` instead of `~/Library/Logs/Video Downloader/`

## v1.0.0 - Initial macOS App Bundle

- macOS `.app` bundle with bundled yt-dlp and ffmpeg
- GUI with download queue, progress tracking, and settings
- Supports YouTube, Vimeo, Kinescope, GetCourse, and direct HLS streams
