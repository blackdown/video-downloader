"""
Runtime helpers for PyInstaller frozen builds.
"""

import os
import sys
from typing import List


def is_frozen() -> bool:
    """Check if running as a PyInstaller-frozen app."""
    return getattr(sys, "frozen", False)


def _bundle_bin_dir() -> str:
    """Return the directory containing bundled binaries inside the .app."""
    # PyInstaller sets _MEIPASS to the temp extraction dir (onefile) or
    # the app's Resources dir (onedir / .app bundle).  Bundled binaries
    # end up next to the other collected files.
    return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))


def ytdlp_cmd() -> List[str]:
    """Return the command prefix to invoke yt-dlp.

    When frozen, uses the bundled yt-dlp binary shipped inside the .app.
    When running from source, uses ``python -m yt_dlp``.
    """
    if is_frozen():
        return [os.path.join(_bundle_bin_dir(), "yt-dlp")]
    return [sys.executable, "-m", "yt_dlp"]


def ffmpeg_env() -> dict:
    """Return an env dict that puts the bundled ffmpeg on PATH.

    yt-dlp finds ffmpeg via PATH, so we prepend the bundle directory.
    When running from source, returns the normal environment unchanged.

    When frozen, also strips PyInstaller-internal env vars so that the
    bundled yt-dlp (which is itself a PyInstaller binary) boots cleanly
    instead of trying to reuse the parent process's ``_MEIPASS`` directory.
    """
    env = os.environ.copy()
    if is_frozen():
        bin_dir = _bundle_bin_dir()
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        # Remove PyInstaller env vars that confuse child PyInstaller binaries
        for key in list(env.keys()):
            if key.startswith(("_MEIPASS", "_PYI", "__PYINSTALLER")):
                del env[key]
        # Remove injected dylib paths that could make the child load wrong libs
        for key in ("DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH"):
            env.pop(key, None)
    return env
