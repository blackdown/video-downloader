"""
Build script for creating a standalone Windows executable.
Bundles yt-dlp, ffmpeg, and Playwright Chromium browser.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Paths
PROJECT_DIR = Path(__file__).parent
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
BUNDLE_DIR = PROJECT_DIR / "bundle"  # For external tools


def run_command(cmd, description):
    """Run a command and check for errors."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")
    print(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"  ERROR: {description} failed!")
        sys.exit(1)
    print(f"  Done.")


def download_ffmpeg():
    """Download ffmpeg if not present."""
    ffmpeg_dir = BUNDLE_DIR / "ffmpeg"
    ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"

    if ffmpeg_exe.exists():
        print(f"  ffmpeg already exists at {ffmpeg_exe}")
        return ffmpeg_dir

    print("  Downloading ffmpeg...")
    ffmpeg_dir.mkdir(parents=True, exist_ok=True)

    # Download from gyan.dev (reliable Windows builds)
    import urllib.request
    import zipfile

    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = BUNDLE_DIR / "ffmpeg.zip"

    print(f"  Downloading from {url}...")
    urllib.request.urlretrieve(url, zip_path)

    print("  Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Extract just the bin folder contents
        for member in zf.namelist():
            if '/bin/' in member and member.endswith('.exe'):
                # Extract to ffmpeg_dir with flat structure
                filename = os.path.basename(member)
                with zf.open(member) as src, open(ffmpeg_dir / filename, 'wb') as dst:
                    dst.write(src.read())

    zip_path.unlink()
    print(f"  ffmpeg installed to {ffmpeg_dir}")
    return ffmpeg_dir


def download_ytdlp():
    """Download yt-dlp if not present."""
    ytdlp_dir = BUNDLE_DIR / "yt-dlp"
    ytdlp_exe = ytdlp_dir / "yt-dlp.exe"

    if ytdlp_exe.exists():
        print(f"  yt-dlp already exists at {ytdlp_exe}")
        return ytdlp_dir

    print("  Downloading yt-dlp...")
    ytdlp_dir.mkdir(parents=True, exist_ok=True)

    import urllib.request
    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

    print(f"  Downloading from {url}...")
    urllib.request.urlretrieve(url, ytdlp_exe)

    print(f"  yt-dlp installed to {ytdlp_dir}")
    return ytdlp_dir


def get_playwright_chromium():
    """Get the path to Playwright's Chromium installation."""
    # Playwright stores browsers in a specific location
    if sys.platform == "win32":
        browsers_path = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    else:
        browsers_path = Path.home() / ".cache" / "ms-playwright"

    if not browsers_path.exists():
        print("  Playwright browsers not found. Installing...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])

    # Find chromium directory
    for item in browsers_path.iterdir():
        if item.is_dir() and "chromium" in item.name.lower():
            print(f"  Found Playwright Chromium at {item}")
            return item

    print("  ERROR: Could not find Playwright Chromium!")
    return None


def create_spec_file(ffmpeg_dir, ytdlp_dir, chromium_dir):
    """Create PyInstaller spec file."""
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# Data files to include
datas = [
    # Include the core and gui packages
]

# Binary files to include
binaries = []

# Add ffmpeg
ffmpeg_path = r"{ffmpeg_dir}"
if os.path.exists(ffmpeg_path):
    for f in os.listdir(ffmpeg_path):
        if f.endswith('.exe'):
            binaries.append((os.path.join(ffmpeg_path, f), 'ffmpeg'))

# Add yt-dlp
ytdlp_path = r"{ytdlp_dir}"
if os.path.exists(ytdlp_path):
    for f in os.listdir(ytdlp_path):
        if f.endswith('.exe'):
            binaries.append((os.path.join(ytdlp_path, f), 'yt-dlp'))

a = Analysis(
    ['video_dl_gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'customtkinter',
        'yt_dlp',
        'playwright',
        'playwright.sync_api',
        'browser_cookie3',
        'requests',
        'PIL',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VideoDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)
'''

    spec_path = PROJECT_DIR / "VideoDownloader.spec"
    with open(spec_path, 'w') as f:
        f.write(spec_content)

    print(f"  Created spec file: {spec_path}")
    return spec_path


def build():
    """Main build function."""
    print("\n" + "="*60)
    print("  VIDEO DOWNLOADER - BUILD SCRIPT")
    print("="*60)

    # Create bundle directory
    BUNDLE_DIR.mkdir(exist_ok=True)

    # Step 1: Download/check dependencies
    print("\n[1/5] Checking dependencies...")

    print("\n  Checking ffmpeg...")
    ffmpeg_dir = download_ffmpeg()

    print("\n  Checking yt-dlp...")
    ytdlp_dir = download_ytdlp()

    print("\n  Checking Playwright Chromium...")
    chromium_dir = get_playwright_chromium()

    # Step 2: Install PyInstaller if needed
    print("\n[2/5] Checking PyInstaller...")
    try:
        import PyInstaller
        print(f"  PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("  Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Step 3: Create spec file
    print("\n[3/5] Creating spec file...")
    spec_path = create_spec_file(ffmpeg_dir, ytdlp_dir, chromium_dir)

    # Step 4: Run PyInstaller
    print("\n[4/5] Building executable...")
    run_command(
        [sys.executable, "-m", "PyInstaller", "--clean", str(spec_path)],
        "PyInstaller build"
    )

    # Step 5: Copy Playwright browsers to dist
    print("\n[5/5] Copying Playwright browsers...")
    if chromium_dir:
        dest_browsers = DIST_DIR / "playwright-browsers"
        if dest_browsers.exists():
            shutil.rmtree(dest_browsers)
        shutil.copytree(chromium_dir, dest_browsers / chromium_dir.name)
        print(f"  Copied Chromium to {dest_browsers}")

        # Create a batch file to set up the browser path
        setup_bat = DIST_DIR / "VideoDownloader.bat"
        with open(setup_bat, 'w') as f:
            f.write('@echo off\n')
            f.write('set PLAYWRIGHT_BROWSERS_PATH=%~dp0playwright-browsers\n')
            f.write('start "" "%~dp0VideoDownloader.exe"\n')
        print(f"  Created launcher: {setup_bat}")

    print("\n" + "="*60)
    print("  BUILD COMPLETE!")
    print("="*60)
    print(f"\n  Output: {DIST_DIR / 'VideoDownloader.exe'}")
    print(f"  Use the .bat file to launch with Playwright support")
    print("")


if __name__ == "__main__":
    build()
