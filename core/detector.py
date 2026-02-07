"""
Vimeo URL detection and video type classification.
"""

import re
import requests
from typing import Tuple, Optional, List
from enum import Enum


class VimeoType(Enum):
    PUBLIC = "public"
    PASSWORD_PROTECTED = "password_protected"
    LOGIN_REQUIRED = "login_required"
    EMBED_ONLY = "embed_only"
    INVALID = "invalid"


class VideoSource(Enum):
    """Identifies the source platform of the video."""
    VIMEO = "vimeo"
    YOUTUBE = "youtube"
    KINESCOPE = "kinescope"
    GETCOURSE = "getcourse"
    DIRECT_STREAM = "direct_stream"
    WEBPAGE = "webpage"  # Generic webpage that may contain embedded videos
    UNKNOWN = "unknown"


class VimeoDetector:
    """Detect video type and extract metadata from various platforms."""

    # URL patterns
    VIMEO_URL_PATTERN = r'vimeo\.com/(?:video/)?(\d+)(?:/([a-f0-9]+))?'
    PLAYER_URL_PATTERN = r'player\.vimeo\.com/video/(\d+)'
    CDN_URL_PATTERN = r'vimeocdn\.com/.+\.m3u8'
    KINESCOPE_URL_PATTERN = r'kinescope\.io/([a-f0-9-]+)/media\.m3u8'
    # YouTube patterns: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID, youtube.com/shorts/ID
    YOUTUBE_URL_PATTERN = r'(?:youtube\.com/(?:watch\?.*v=|embed/|v/|shorts/)|youtu\.be/)([\w-]{11})'
    # GetCourse video hosting: vh-api-X-XX.gceuproxy.com/api/playlist/master/ID1/ID2
    GETCOURSE_URL_PATTERN = r'gceuproxy\.com/api/playlist/master/([a-f0-9]+)/([a-f0-9]+)'
    
    def __init__(self, url: str, cookies=None):
        self.url = url
        self.cookies = cookies
        self.video_id = None
        self.hash = None
        self.video_type = None
        self.source = VideoSource.UNKNOWN
        
    def parse_url(self) -> Tuple[Optional[str], Optional[str]]:
        """Extract video ID and hash from URL."""

        # Try standard vimeo.com pattern
        match = re.search(self.VIMEO_URL_PATTERN, self.url)
        if match:
            self.video_id = match.group(1)
            self.hash = match.group(2) if match.group(2) else None
            self.source = VideoSource.VIMEO
            return self.video_id, self.hash

        # Try player.vimeo.com pattern
        match = re.search(self.PLAYER_URL_PATTERN, self.url)
        if match:
            self.video_id = match.group(1)
            self.source = VideoSource.VIMEO
            return self.video_id, None

        # Try YouTube URL pattern
        match = re.search(self.YOUTUBE_URL_PATTERN, self.url)
        if match:
            self.video_id = match.group(1)
            self.source = VideoSource.YOUTUBE
            self.video_type = VimeoType.PUBLIC
            return self.video_id, None

        # Try GetCourse URL pattern
        match = re.search(self.GETCOURSE_URL_PATTERN, self.url)
        if match:
            self.video_id = match.group(1)[:8]  # First 8 chars of first ID
            self.source = VideoSource.GETCOURSE
            self.video_type = VimeoType.PUBLIC
            return self.video_id, None

        # Try Kinescope URL pattern
        match = re.search(self.KINESCOPE_URL_PATTERN, self.url)
        if match:
            self.video_id = match.group(1)
            self.source = VideoSource.KINESCOPE
            self.video_type = VimeoType.PUBLIC
            return self.video_id, None

        # Try direct CDN m3u8 URL (Vimeo CDN)
        if re.search(self.CDN_URL_PATTERN, self.url):
            self.video_id = "direct_m3u8"
            self.source = VideoSource.DIRECT_STREAM
            self.video_type = VimeoType.PUBLIC
            self.is_master_playlist = self._check_is_master_playlist()
            return self.video_id, None

        return None, None

    def _check_is_master_playlist(self) -> bool:
        """Check if URL is a master playlist (has audio) vs video-only component."""
        # Kinescope video-only streams have type=video in query string
        if 'type=video' in self.url:
            return False
        # Vimeo master playlists typically have these patterns
        if '/primary/' in self.url and 'playlist.m3u8' in self.url:
            return True
        # Vimeo video-only components have these patterns
        if 'st=video' in self.url or 'media.m3u8' in self.url:
            if '/primary/' not in self.url:
                return False
        return True  # Assume master if unsure

    def is_video_only_stream(self) -> bool:
        """Returns True if this appears to be a video-only stream URL."""
        if not hasattr(self, 'is_master_playlist'):
            self.is_master_playlist = self._check_is_master_playlist()
        return not self.is_master_playlist
    
    def detect_type(self) -> VimeoType:
        """Detect the video access type."""
        
        if not self.video_id:
            self.parse_url()
            
        if not self.video_id:
            return VimeoType.INVALID
        
        # Construct the public URL
        if self.hash:
            check_url = f"https://vimeo.com/{self.video_id}/{self.hash}"
        else:
            check_url = f"https://vimeo.com/{self.video_id}"
        
        try:
            # First check: no authentication
            response = requests.get(check_url, timeout=10, allow_redirects=True)
            
            # Check for password form
            if 'password' in response.text.lower() and 'enter password' in response.text.lower():
                return VimeoType.PASSWORD_PROTECTED
            
            # Check for login requirement
            if 'log in' in response.text.lower() or 'sign in' in response.text.lower():
                if 'watch this video' in response.text.lower():
                    return VimeoType.LOGIN_REQUIRED
            
            # Check if it's embed-only
            if 'Sorry' in response.text and 'cannot be played' in response.text:
                return VimeoType.EMBED_ONLY
            
            # If we can see player config or video data, it's accessible
            if 'player.vimeo.com' in response.text or '"config_url"' in response.text:
                return VimeoType.PUBLIC
            
            # Try with cookies if provided
            if self.cookies:
                response = requests.get(check_url, cookies=self.cookies, timeout=10)
                if response.status_code == 200:
                    return VimeoType.PUBLIC
            
            return VimeoType.LOGIN_REQUIRED
            
        except requests.RequestException:
            # If we can't check, assume it might work with cookies
            return VimeoType.PUBLIC
    
    def get_public_url(self) -> str:
        """Get the canonical public URL."""
        if self.hash:
            return f"https://vimeo.com/{self.video_id}/{self.hash}"
        return f"https://vimeo.com/{self.video_id}"
    
    def get_player_url(self) -> str:
        """Get the player embed URL."""
        return f"https://player.vimeo.com/video/{self.video_id}"


class WebpageScraper:
    """Scrape webpages to find embedded video URLs."""

    # Patterns to find video URLs in HTML/JS
    PATTERNS = [
        # GetCourse: vh-api-X-XX.gceuproxy.com/api/playlist/master/ID1/ID2
        (r'(https?://[a-z0-9-]+\.gceuproxy\.com/api/playlist/master/[a-f0-9]+/[a-f0-9]+[^"\'\s]*)', VideoSource.GETCOURSE),
        # Kinescope: kinescope.io/ID/media.m3u8
        (r'(https?://kinescope\.io/[a-f0-9-]+/media\.m3u8[^"\'\s]*)', VideoSource.KINESCOPE),
        # Vimeo player iframe
        (r'(https?://player\.vimeo\.com/video/\d+[^"\'\s]*)', VideoSource.VIMEO),
        # Vimeo CDN m3u8
        (r'(https?://[a-z0-9-]+\.vimeocdn\.com/[^"\'\s]+\.m3u8[^"\'\s]*)', VideoSource.DIRECT_STREAM),
        # YouTube embed
        (r'(https?://(?:www\.)?youtube\.com/embed/[\w-]{11}[^"\'\s]*)', VideoSource.YOUTUBE),
        # Generic m3u8 URLs
        (r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', VideoSource.DIRECT_STREAM),
    ]

    def __init__(self, url: str, cookies: dict = None, browser: str = "chrome"):
        self.url = url
        self.cookies = cookies or {}
        self.browser = browser
        self.found_urls: List[Tuple[str, VideoSource]] = []

    def fetch_and_scan(self) -> List[Tuple[str, VideoSource]]:
        """Fetch the webpage and scan for video URLs."""
        # First try yt-dlp with browser cookies (handles auth better)
        found = self._try_ytdlp_extract()
        if found:
            self.found_urls = found
            return found

        # Fall back to requests-based scraping
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(self.url, cookies=self.cookies, headers=headers, timeout=15)
            response.raise_for_status()

            html = response.text
            self.found_urls = self._scan_html(html)
            return self.found_urls

        except requests.RequestException as e:
            print(f"Warning: Could not fetch webpage: {e}")
            return []

    def _try_ytdlp_extract(self) -> List[Tuple[str, VideoSource]]:
        """Try to extract video URL using yt-dlp's generic extractor."""
        import subprocess
        import json
        from .runtime import ytdlp_cmd, ffmpeg_env

        try:
            cmd = [
                *ytdlp_cmd(),
                "--cookies-from-browser", self.browser,
                "--dump-json",
                "--no-download",
                "--no-warnings",
                "--ignore-errors",
                "-q",
                self.url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=ffmpeg_env())

            if result.returncode == 0 and result.stdout.strip():
                # yt-dlp found something - parse the JSON
                try:
                    info = json.loads(result.stdout.strip().split('\n')[0])
                    video_url = info.get('url') or info.get('webpage_url') or self.url

                    # Determine source from the URL or extractor
                    extractor = info.get('extractor', '').lower()
                    if 'getcourse' in extractor or 'gceuproxy' in video_url:
                        source = VideoSource.GETCOURSE
                    elif 'kinescope' in extractor or 'kinescope' in video_url:
                        source = VideoSource.KINESCOPE
                    elif 'vimeo' in extractor or 'vimeo' in video_url:
                        source = VideoSource.VIMEO
                    elif 'youtube' in extractor or 'youtube' in video_url:
                        source = VideoSource.YOUTUBE
                    else:
                        source = VideoSource.DIRECT_STREAM

                    print(f"yt-dlp found video: {extractor or 'generic'}")
                    return [(video_url, source)]

                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            print("Warning: yt-dlp extraction timed out")
        except Exception as e:
            print(f"Warning: yt-dlp extraction failed: {e}")

        return []

    def _scan_html(self, html: str) -> List[Tuple[str, VideoSource]]:
        """Scan HTML content for video URLs."""
        found = []
        seen_urls = set()

        for pattern, source in self.PATTERNS:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for url in matches:
                # Clean up URL (remove trailing quotes, escapes)
                url = url.rstrip('"\'\\ ')
                url = url.replace('\\/', '/')  # Unescape JSON

                if url not in seen_urls:
                    seen_urls.add(url)
                    found.append((url, source))

        # Prioritize: GetCourse > Kinescope > Vimeo > YouTube > generic m3u8
        priority = {
            VideoSource.GETCOURSE: 0,
            VideoSource.KINESCOPE: 1,
            VideoSource.VIMEO: 2,
            VideoSource.YOUTUBE: 3,
            VideoSource.DIRECT_STREAM: 4,
        }
        found.sort(key=lambda x: priority.get(x[1], 99))

        return found

    def get_best_url(self) -> Optional[Tuple[str, VideoSource]]:
        """Get the best video URL found (highest priority)."""
        if self.found_urls:
            return self.found_urls[0]
        return None
