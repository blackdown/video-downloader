#!/usr/bin/env python3
"""
Quick test to verify the module structure works correctly.
"""

import sys

print("Testing Video Downloader imports...\n")

# Test imports
try:
    from core.detector import VimeoDetector, VimeoType, VideoSource
    print("[OK] detector.py imports successfully")
except ImportError as e:
    print(f"[FAIL] detector.py import failed: {e}")
    sys.exit(1)

try:
    from core.auth import CookieManager
    print("[OK] auth.py imports successfully")
except ImportError as e:
    print(f"[FAIL] auth.py import failed: {e}")
    sys.exit(1)

try:
    from core.commands import CommandBuilder
    print("[OK] commands.py imports successfully")
except ImportError as e:
    print(f"[FAIL] commands.py import failed: {e}")
    sys.exit(1)

try:
    from core.downloader import VimeoDownloader
    print("[OK] downloader.py imports successfully")
except ImportError as e:
    print(f"[FAIL] downloader.py import failed: {e}")
    sys.exit(1)

print("\n--- Testing URL parsing ---")

# Test Vimeo URL
detector = VimeoDetector("https://vimeo.com/123456789/abcdef123")
video_id, hash_val = detector.parse_url()
print(f"Vimeo - Video ID: {video_id}, Hash: {hash_val}, Source: {detector.source.value}")

# Test Kinescope URL
kinescope_url = "https://kinescope.io/a1b2c3d4-e5f6-7890-abcd-ef1234567890/media.m3u8?quality=auto&type=video"
detector2 = VimeoDetector(kinescope_url)
video_id2, _ = detector2.parse_url()
print(f"Kinescope - Video ID: {video_id2[:8]}..., Source: {detector2.source.value}")

print("\n--- Testing cookie manager ---")
cookie_manager = CookieManager("chrome")
profile = cookie_manager.get_chrome_profile_number()
print(f"Detected Chrome profile: {profile}")
cookie_string = cookie_manager.get_cookie_string_for_ytdlp()
print(f"Cookie string for yt-dlp: {cookie_string}")

print("\n--- Testing command builder ---")
builder = CommandBuilder(
    video_id="123456789",
    video_hash="abcdef",
    video_type=VimeoType.PUBLIC,
    cookie_string="chrome:Default"
)
cmd = builder.build_ytdlp_command()
print(f"Generated command has {len(cmd)} arguments")
print(f"Command preview: {' '.join(cmd[:5])}...")

print("\n[OK] All basic tests passed!")
print("\nNext steps:")
print("1. Install dependencies: pip install -r requirements.txt")
print("2. Install yt-dlp and ffmpeg on your system")
print("3. Run: python vimeo_dl.py --help")
