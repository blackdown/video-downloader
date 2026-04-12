"""
Browser-based video detection using Playwright.
Intercepts network requests to find video URLs on pages that require authentication.
"""

import os
import re
import sys
import shutil
import threading
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Request


def _setup_bundled_browsers():
    """Set up Playwright browsers path for bundled exe."""
    if getattr(sys, 'frozen', False):
        # Running as bundled exe
        exe_dir = Path(sys.executable).parent
        browsers_dir = exe_dir / "playwright-browsers"
        if browsers_dir.exists() and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)
            print(f"[Playwright] Using bundled browsers: {browsers_dir}")


def _get_real_browser_exe() -> Optional[str]:
    """
    Return the path to a real Chrome or Edge executable, preferring Chrome.
    Using a real browser binary avoids Cloudflare bot detection.
    """
    if os.name == 'nt':
        candidates = [
            # Chrome
            Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
            Path(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
            # Edge fallback
            Path(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe',
            Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe',
        ]
    else:
        import shutil
        for cmd in ['google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium']:
            found = shutil.which(cmd)
            if found:
                print(f"[Detect] Found browser: {found}")
                return found
        return None

    for p in candidates:
        if p.exists():
            print(f"[Detect] Using browser: {p}")
            return str(p)
    return None


# Set up browsers path before importing playwright
_setup_bundled_browsers()

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    from playwright_stealth import Stealth
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


# Directory for app-specific browser profile
def get_detection_profile_dir() -> Path:
    """Get the directory for the detection browser profile."""
    # Store in user's app data
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home()))
    else:
        base = Path.home() / '.local' / 'share'
    return base / 'VideoDownloader' / 'detection-profile'


def is_detection_profile_setup() -> bool:
    """Check if the detection profile has been set up."""
    profile_dir = get_detection_profile_dir()
    # Check for a marker file that indicates setup is complete
    return (profile_dir / '.profile-ready').exists()


def reset_detection_profile() -> None:
    """Reset the detection profile (remove the ready marker)."""
    profile_dir = get_detection_profile_dir()
    ready_file = profile_dir / '.profile-ready'
    if ready_file.exists():
        ready_file.unlink()
        print(f"[Setup] Profile reset - will need to log in again")


def setup_detection_profile(on_complete: Optional[Callable[[bool, str], None]] = None) -> None:
    """
    Set up the detection profile by launching a browser for the user to log in.

    Args:
        on_complete: Callback(success, message) when setup is complete
    """
    def run_setup():
        import subprocess
        import time

        profile_dir = get_detection_profile_dir()
        profile_dir.mkdir(parents=True, exist_ok=True)

        exe = _get_real_browser_exe()
        if not exe:
            if on_complete:
                on_complete(False, "No Chrome or Edge installation found.")
            return

        print(f"[Setup] Launching browser (no automation): {exe}")
        print("")
        print("=" * 50)
        print("SETUP: Log in to your video sites in the browser window.")
        print("Close the browser window when you're done.")
        print("=" * 50)

        try:
            # Launch Chrome/Edge as a plain process — no CDP, invisible to Cloudflare
            proc = subprocess.Popen([
                exe,
                f'--user-data-dir={profile_dir}',
                '--no-first-run',
                '--no-default-browser-check',
                'about:blank',
            ])
            print(f"[Setup] Browser open (PID {proc.pid}). Waiting for close...")
            proc.wait()
            print("[Setup] Browser closed, saving profile...")

            (profile_dir / '.profile-ready').touch()
            print("[Setup] Profile saved successfully!")

            if on_complete:
                on_complete(True, "Profile setup complete! You can now detect videos.")

        except Exception as e:
            print(f"[Setup] Error: {e}")
            if on_complete:
                on_complete(False, f"Setup failed: {e}")

    # Run in thread to not block UI
    thread = threading.Thread(target=run_setup, daemon=True)
    thread.start()
    return thread


@dataclass
class DetectedVideo:
    """Represents a detected video URL."""
    url: str
    source: str  # e.g., "cloudflare", "vimeo", "youtube", "m3u8"
    quality: Optional[str] = None  # e.g., "1080p", "720p"
    is_master: bool = True  # True if this is a master playlist (has audio)
    title: Optional[str] = None
    page_url: Optional[str] = None


class BrowserDetector:
    """
    Detects video URLs by intercepting browser network requests.
    Uses Playwright with existing browser profiles to access authenticated pages.
    """

    # URL patterns to capture
    VIDEO_PATTERNS = [
        (r'cloudflarestream\.com/[^/]+/manifest/video\.m3u8', 'cloudflare'),
        (r'stream\.mux\.com/[^"\'\s?]+\.m3u8', 'mux'),
        (r'player\.vimeo\.com/video/\d+', 'vimeo'),
        (r'vimeocdn\.com/.*\.m3u8', 'vimeo'),
        (r'youtube\.com/watch\?v=', 'youtube'),
        (r'googlevideo\.com/.*\.m3u8', 'youtube'),
        (r'kinescope\.io/[^/]+/media\.m3u8', 'kinescope'),
        (r'gceuproxy\.com/api/playlist/master/', 'getcourse'),
        (r'\.m3u8(?:\?|$)', 'generic'),
    ]

    def __init__(self, browser: str = "chrome", headless: bool = False):
        """
        Initialize the browser detector.

        Args:
            browser: Browser to use ("chrome", "firefox", "edge")
            headless: Run in headless mode (may not work with all sites)
        """
        self.browser = browser.lower()
        self.headless = headless
        self._detected_videos: List[DetectedVideo] = []
        self._seen_urls: set = set()
        self._page_title: Optional[str] = None
        self._progress_callback: Optional[Callable[[str], None]] = None
        self._video_found_callback: Optional[Callable[["DetectedVideo"], None]] = None

    def get_browser_profile_path(self) -> Optional[str]:
        """Get the path to the browser's user data directory."""
        if os.name == 'nt':  # Windows
            localappdata = os.environ.get('LOCALAPPDATA', '')
            appdata = os.environ.get('APPDATA', '')

            if self.browser == "chrome":
                path = Path(localappdata) / 'Google' / 'Chrome' / 'User Data'
            elif self.browser == "firefox":
                # Firefox uses profiles differently - find the default profile
                # First check standard installation
                profiles_path = Path(appdata) / 'Mozilla' / 'Firefox' / 'Profiles'

                # If not found, check Microsoft Store installation
                if not profiles_path.exists():
                    packages_path = Path(localappdata) / 'Packages'
                    if packages_path.exists():
                        for pkg in packages_path.iterdir():
                            if 'firefox' in pkg.name.lower() or 'mozilla' in pkg.name.lower():
                                store_profiles = pkg / 'LocalCache' / 'Roaming' / 'Mozilla' / 'Firefox' / 'Profiles'
                                if store_profiles.exists():
                                    profiles_path = store_profiles
                                    break

                if profiles_path.exists():
                    # Find default profile (prefer .default-release, then .default)
                    for suffix in ['.default-release', '.default']:
                        for profile in profiles_path.iterdir():
                            if profile.is_dir() and profile.name.endswith(suffix):
                                return str(profile)
                    # Fallback: any profile with 'default' in name
                    for profile in profiles_path.iterdir():
                        if profile.is_dir() and 'default' in profile.name.lower():
                            return str(profile)
                return None
            elif self.browser == "edge":
                path = Path(localappdata) / 'Microsoft' / 'Edge' / 'User Data'
            else:
                return None

            return str(path) if path.exists() else None
        else:
            # macOS/Linux paths
            home = Path.home()
            if self.browser == "chrome":
                if os.name == 'darwin':
                    path = home / 'Library' / 'Application Support' / 'Google' / 'Chrome'
                else:
                    path = home / '.config' / 'google-chrome'
            elif self.browser == "firefox":
                if os.name == 'darwin':
                    path = home / 'Library' / 'Application Support' / 'Firefox' / 'Profiles'
                else:
                    path = home / '.mozilla' / 'firefox'
                # Find default profile
                if path.exists():
                    for profile in path.iterdir():
                        if profile.is_dir() and 'default' in profile.name.lower():
                            return str(profile)
                return None
            else:
                return None

            return str(path) if path.exists() else None

    def _handle_request(self, request: "Request") -> None:
        """Handle intercepted network request."""
        url = request.url

        # Skip if already seen
        if url in self._seen_urls:
            return

        # Check against patterns
        for pattern, source in self.VIDEO_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                self._seen_urls.add(url)

                # Determine if this is a master playlist
                is_master = True
                quality = None

                if 'cloudflarestream' in url:
                    # Master playlists end with /manifest/video.m3u8
                    is_master = url.endswith('/manifest/video.m3u8')
                    if not is_master:
                        # Try to extract quality from URL
                        if '_r' in url:
                            # Quality info might be in the filename
                            pass

                video = DetectedVideo(
                    url=url,
                    source=source,
                    is_master=is_master,
                    quality=quality,
                    title=self._page_title,
                    page_url=None,  # Will be set after detection
                )
                self._detected_videos.append(video)
                print(f"[Detect] Found video #{len(self._detected_videos)}: {source} - {url[:80]}...")

                if self._progress_callback:
                    self._progress_callback(f"Found {len(self._detected_videos)} video(s)")

                # Real-time callback for UI updates
                if self._video_found_callback:
                    self._video_found_callback(video)

                break

    def detect_videos(
        self,
        url: str,
        timeout: int = 15000,
        progress_callback: Optional[Callable[[str], None]] = None,
        video_found_callback: Optional[Callable[["DetectedVideo"], None]] = None,
        use_dedicated_profile: bool = True
    ) -> List[DetectedVideo]:
        """
        Detect video URLs on a page by intercepting network requests.

        Args:
            url: The page URL to scan
            timeout: How long to wait for video requests (milliseconds)
            progress_callback: Optional callback for progress updates
            video_found_callback: Optional callback when a video is found (for real-time UI)
            use_dedicated_profile: Use the app's dedicated profile (doesn't require closing browser)

        Returns:
            List of detected video URLs
        """
        if not HAS_PLAYWRIGHT:
            raise ImportError(
                "Playwright is not installed. "
                "Install it with: pip install playwright && playwright install chromium"
            )

        self._detected_videos = []
        self._seen_urls = set()
        self._page_title = None
        self._progress_callback = progress_callback
        self._video_found_callback = video_found_callback

        # Determine which profile to use
        if use_dedicated_profile:
            profile_path = str(get_detection_profile_dir())
            print(f"[Detect] Using dedicated profile at: {profile_path}")
            if not is_detection_profile_setup():
                raise RuntimeError(
                    "Detection profile not set up yet.\n"
                    "Click 'Setup Profile' to log in first."
                )
            if progress_callback:
                progress_callback("Launching detection browser...")
        else:
            profile_path = self.get_browser_profile_path()
            if not profile_path:
                raise RuntimeError(
                    f"Could not find {self.browser.title()} profile directory.\n"
                    f"Make sure {self.browser.title()} is installed and has been run at least once.\n"
                    f"Or try a different browser (Chrome/Edge) in settings."
                )
            if progress_callback:
                progress_callback(f"Launching {self.browser}...")

        with sync_playwright() as p:
            if HAS_STEALTH:
                Stealth().hook_playwright_context(p)
                print("[Detect] Stealth mode active")

            # Launch browser with profile
            try:
                if use_dedicated_profile:
                    # Prefer a real browser binary to avoid Cloudflare bot detection
                    exe = _get_real_browser_exe()
                    if exe:
                        print(f"[Detect] Launching with real browser: {exe}")
                    else:
                        print(f"[Detect] Launching Playwright Chromium (no real browser found)...")
                    launch_kwargs = dict(
                        user_data_dir=profile_path,
                        headless=self.headless,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--no-first-run',
                            '--no-default-browser-check',
                        ],
                        ignore_default_args=['--enable-automation'],
                        viewport={'width': 1280, 'height': 800},
                    )
                    if exe:
                        launch_kwargs['executable_path'] = exe
                    browser = p.chromium.launch_persistent_context(**launch_kwargs)
                    print(f"[Detect] Browser launched, pages: {len(browser.pages)}")
                elif self.browser == "firefox":
                    # Firefox uses a different approach
                    browser = p.firefox.launch_persistent_context(
                        user_data_dir=profile_path,
                        headless=self.headless,
                        viewport={'width': 1280, 'height': 800},
                    )
                else:
                    # Chrome/Edge with stealth settings — use executable_path for reliability
                    exe = _get_real_browser_exe()
                    browser = p.chromium.launch_persistent_context(
                        user_data_dir=profile_path,
                        executable_path=exe,
                        headless=self.headless,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                        ],
                        ignore_default_args=['--enable-automation'],
                        viewport={'width': 1280, 'height': 800},
                    )
            except Exception as e:
                error_msg = str(e)
                # Log the full error for debugging
                print(f"[DEBUG] Browser launch error: {error_msg[:500]}")

                if "Target page, context or browser has been closed" in error_msg:
                    raise RuntimeError(
                        f"Cannot access {self.browser} profile - the browser appears to be running.\n"
                        f"Please close {self.browser.title()} completely (including system tray) and try again."
                    )
                elif "user data directory is already in use" in error_msg.lower():
                    raise RuntimeError(
                        f"{self.browser.title()} is currently running.\n"
                        f"Please close it completely and try again."
                    )
                elif "process did exit" in error_msg.lower():
                    # Browser crashed during launch
                    raise RuntimeError(
                        f"{self.browser.title()} crashed during launch.\n"
                        f"Make sure {self.browser.title()} is completely closed and try again."
                    )
                else:
                    raise

            try:
                # Create a new page for detection
                page = browser.new_page()
                print(f"[Detect] Created new page (total: {len(browser.pages)})")

                # Intercept network requests
                page.on("request", self._handle_request)

                # Normalize URL - remove /en/ prefix which can cause redirect issues
                normalized_url = url.replace('/en/', '/').replace('/projects', '')
                if normalized_url != url:
                    print(f"[Detect] Normalized URL: {normalized_url}")

                if progress_callback:
                    progress_callback(f"Loading page...")

                # Navigate to the page
                print(f"[Detect] Loading: {normalized_url}")
                try:
                    page.goto(normalized_url, wait_until="domcontentloaded", timeout=30000)
                except Exception as nav_err:
                    print(f"[Detect] Navigation issue: {nav_err}")
                    # Try original URL if normalized failed
                    if normalized_url != url:
                        print(f"[Detect] Trying original URL: {url}")
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Check for Cloudflare challenge and wait for it to complete
                if progress_callback:
                    progress_callback("Checking for security challenge...")
                try:
                    # Look for Cloudflare challenge indicators
                    for i in range(60):  # Wait up to 60 seconds
                        title = page.title().lower()

                        if "just a moment" in title or "checking" in title:
                            if i % 5 == 0:  # Log every 5 seconds
                                print(f"[Detect] Waiting for Cloudflare challenge... ({i}s)")
                                if progress_callback:
                                    progress_callback(f"Waiting for security check... ({i}s)")
                            page.wait_for_timeout(1000)
                        else:
                            print(f"[Detect] Page loaded: {title[:50]}")
                            break
                except Exception as cf_err:
                    print(f"[Detect] Challenge check error: {cf_err}")

                # Get page title
                try:
                    self._page_title = page.title()
                except:
                    pass

                if progress_callback:
                    progress_callback(f"Waiting for video requests...")

                # Wait for network to be idle (video requests to complete)
                try:
                    page.wait_for_load_state("networkidle", timeout=timeout)
                except:
                    pass  # Timeout is OK, we might have captured what we need

                # Additional wait in case video loads lazily
                page.wait_for_timeout(2000)

                # Try clicking play button if video hasn't loaded
                if not self._detected_videos:
                    if progress_callback:
                        progress_callback("Trying to trigger video load...")
                    try:
                        # Common play button selectors
                        play_selectors = [
                            'button[aria-label*="play" i]',
                            'button[class*="play" i]',
                            '.vjs-big-play-button',
                            '.play-button',
                            '[data-testid="play-button"]',
                        ]
                        for selector in play_selectors:
                            try:
                                play_btn = page.locator(selector).first
                                if play_btn.is_visible(timeout=1000):
                                    play_btn.click()
                                    page.wait_for_timeout(3000)
                                    break
                            except:
                                continue
                    except:
                        pass

                # Try to find and click through all lessons/chapters to capture all videos
                initial_count = len(self._detected_videos)
                if progress_callback:
                    progress_callback(f"Looking for lesson list... (found {initial_count} so far)")

                try:
                    # Skillshare-specific: find lesson title links (not SVGs or icons)
                    lesson_selectors = [
                        # Skillshare - target the clickable title/link, not the container
                        '[class*="session-item"] [class*="title"]',
                        '[class*="session-item"] a',
                        '[class*="session-item"] button',
                        '[class*="lesson-item"] a',
                        '[class*="lesson-item"] [class*="title"]',
                        # Generic patterns
                        '[class*="chapter-item"] a',
                        '[class*="playlist-item"] a',
                        '.curriculum-item a',
                    ]

                    lessons_found = []
                    used_selector = None
                    for selector in lesson_selectors:
                        try:
                            items = page.locator(selector).all()
                            # Filter to only visible items
                            visible_items = [item for item in items if item.is_visible()]
                            if len(visible_items) > 1:  # Found a list
                                lessons_found = visible_items
                                used_selector = selector
                                print(f"[Detect] Found {len(visible_items)} visible lessons with: {selector}")
                                break
                        except:
                            continue

                    if lessons_found and len(lessons_found) > 1:
                        if progress_callback:
                            progress_callback(f"Found {len(lessons_found)} lessons, scanning...")

                        for i, lesson in enumerate(lessons_found):
                            try:
                                # Quick visibility check
                                if not lesson.is_visible():
                                    print(f"[Detect] Lesson {i+1} not visible, skipping")
                                    continue

                                # Click with short timeout
                                lesson.click(timeout=3000)
                                print(f"[Detect] Clicked lesson {i+1}/{len(lessons_found)}")

                                if progress_callback:
                                    progress_callback(f"Lesson {i+1}/{len(lessons_found)} - {len(self._detected_videos)} videos found")

                                # Brief wait for video request
                                page.wait_for_timeout(1500)

                            except Exception as lesson_err:
                                # Don't log full error, just note it failed
                                print(f"[Detect] Lesson {i+1} skipped")
                                continue

                        print(f"[Detect] Finished scanning. Total videos: {len(self._detected_videos)}")

                except Exception as playlist_err:
                    print(f"[Detect] Playlist scan error: {playlist_err}")

                # Update page_url for all detected videos
                for video in self._detected_videos:
                    video.page_url = url
                    if not video.title:
                        video.title = self._page_title

            finally:
                browser.close()

        # Filter to only return master playlists (with audio)
        master_videos = [v for v in self._detected_videos if v.is_master]

        if progress_callback:
            count = len(master_videos)
            progress_callback(f"Detection complete. Found {count} video(s).")

        return master_videos if master_videos else self._detected_videos


def detect_videos_async(
    url: str,
    browser: str = "chrome",
    headless: bool = False,
    timeout: int = 15000,
    use_dedicated_profile: bool = True,
    on_complete: Optional[Callable[[List[DetectedVideo], Optional[str]], None]] = None,
    on_progress: Optional[Callable[[str], None]] = None,
    on_video_found: Optional[Callable[[DetectedVideo], None]] = None,
) -> threading.Thread:
    """
    Run video detection in a background thread.

    Args:
        url: Page URL to scan
        browser: Browser to use (ignored if use_dedicated_profile=True)
        headless: Run headless
        timeout: Detection timeout
        use_dedicated_profile: Use app's dedicated profile (default True, doesn't require closing browser)
        on_complete: Callback when complete (videos, error_message)
        on_progress: Callback for progress updates

    Returns:
        The thread object (already started)
    """
    def run():
        try:
            detector = BrowserDetector(browser=browser, headless=headless)
            videos = detector.detect_videos(
                url,
                timeout=timeout,
                progress_callback=on_progress,
                video_found_callback=on_video_found,
                use_dedicated_profile=use_dedicated_profile
            )
            if on_complete:
                on_complete(videos, None)
        except Exception as e:
            if on_complete:
                on_complete([], str(e))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


# Check if Playwright is available
def is_playwright_available() -> bool:
    """Check if Playwright is installed and ready."""
    return HAS_PLAYWRIGHT
