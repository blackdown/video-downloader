# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Video Downloader macOS .app bundle.

Build with:
    ./build_macos.sh        (recommended — downloads yt-dlp first)
    pyinstaller video_dl_gui.spec --noconfirm   (if yt-dlp binary already present)

Output:
    dist/Video Downloader.app
"""

import os
import re
import importlib
import subprocess

# ---------------------------------------------------------------------------
# Locate customtkinter package data (themes, assets)
# ---------------------------------------------------------------------------
ctk_path = os.path.dirname(importlib.import_module("customtkinter").__file__)

# ---------------------------------------------------------------------------
# Collect ffmpeg / ffprobe and all their non-system dylib dependencies
# ---------------------------------------------------------------------------

def _resolve(path):
    """Resolve symlinks to the real file."""
    return os.path.realpath(path)


def _collect_dylibs(binary, seen=None):
    """Recursively collect non-system .dylib dependencies of a Mach-O binary."""
    if seen is None:
        seen = set()
    result = subprocess.run(["otool", "-L", binary], capture_output=True, text=True)
    deps = []
    for line in result.stdout.strip().split("\n")[1:]:
        m = re.match(r"\s+(/usr/local/\S+)", line)
        if m:
            real = _resolve(m.group(1))
            if real not in seen and os.path.isfile(real):
                seen.add(real)
                deps.append(real)
                deps.extend(_collect_dylibs(real, seen))
    return deps


def _find_binary(name):
    """Find a binary on PATH, resolving symlinks."""
    result = subprocess.run(["which", name], capture_output=True, text=True)
    path = result.stdout.strip()
    if path and os.path.exists(path):
        return _resolve(path)
    return None


# Collect ffmpeg + ffprobe + all their shared libraries
_external_binaries = []  # list of (src_path, dest_dir_in_bundle)

for tool in ("ffmpeg", "ffprobe"):
    tool_path = _find_binary(tool)
    if tool_path:
        _external_binaries.append((tool_path, "."))
        for dylib in _collect_dylibs(tool_path):
            _external_binaries.append((dylib, "."))

# Deduplicate (ffmpeg and ffprobe share most dylibs)
_seen_srcs = set()
_deduped = []
for src, dst in _external_binaries:
    if src not in _seen_srcs:
        _seen_srcs.add(src)
        _deduped.append((src, dst))
_external_binaries = _deduped

# ---------------------------------------------------------------------------
# Bundle the standalone yt-dlp binary (downloaded by build_macos.sh)
# ---------------------------------------------------------------------------
# NOTE: yt-dlp_macos is itself a PyInstaller-packaged binary.  Including it
# via binaries or datas causes PyInstaller to mangle it during signing.
# Instead, the build script copies it into the .app AFTER PyInstaller runs.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["video_dl_gui.py"],
    pathex=[],
    binaries=_external_binaries,
    datas=[
        # customtkinter needs its assets/ and windows/ directories at runtime
        (ctk_path, "customtkinter"),
    ],
    hiddenimports=[
        "customtkinter",
        # Third-party modules that PyInstaller may not auto-detect
        "rich",
        "rich.console",
        "rich.progress",
        "rich.live",
        "rich.panel",
        "rich.text",
        # Core application modules
        "core",
        "core.auth",
        "core.commands",
        "core.detector",
        "core.downloader",
        "core.runtime",
        "gui",
        "gui.app",
        "gui.managers",
        "gui.managers.download_worker",
        "gui.managers.event_processor",
        "gui.managers.logger",
        "gui.managers.queue_manager",
        "gui.models",
        "gui.models.queue_item",
        "gui.models.settings",
        "gui.widgets",
        "gui.widgets.log_viewer",
        "gui.widgets.queue_item_widget",
        "gui.widgets.queue_list",
        "gui.widgets.settings_panel",
        "gui.widgets.stream_warning",
        "gui.widgets.url_input",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Video Downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No terminal window
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Video Downloader",
)

app = BUNDLE(
    coll,
    name="Video Downloader.app",
    bundle_identifier="com.videodownloader.app",
    info_plist={
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        # Allow Rosetta translation on Apple Silicon when built with x86_64 Python
        "LSArchitecturePriority": ["x86_64"],
    },
)
