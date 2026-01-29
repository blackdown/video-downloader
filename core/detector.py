"""
Vimeo URL detection and video type classification.
"""

import re
import requests
from typing import Tuple, Optional
from enum import Enum


class VimeoType(Enum):
    PUBLIC = "public"
    PASSWORD_PROTECTED = "password_protected"
    LOGIN_REQUIRED = "login_required"
    EMBED_ONLY = "embed_only"
    INVALID = "invalid"


class VimeoDetector:
    """Detect Vimeo video type and extract metadata."""

    # URL patterns
    VIMEO_URL_PATTERN = r'vimeo\.com/(?:video/)?(\d+)(?:/([a-f0-9]+))?'
    PLAYER_URL_PATTERN = r'player\.vimeo\.com/video/(\d+)'
    CDN_URL_PATTERN = r'vimeocdn\.com/.+\.m3u8'
    
    def __init__(self, url: str, cookies=None):
        self.url = url
        self.cookies = cookies
        self.video_id = None
        self.hash = None
        self.video_type = None
        
    def parse_url(self) -> Tuple[Optional[str], Optional[str]]:
        """Extract video ID and hash from URL."""

        # Try standard vimeo.com pattern
        match = re.search(self.VIMEO_URL_PATTERN, self.url)
        if match:
            self.video_id = match.group(1)
            self.hash = match.group(2) if match.group(2) else None
            return self.video_id, self.hash

        # Try player.vimeo.com pattern
        match = re.search(self.PLAYER_URL_PATTERN, self.url)
        if match:
            self.video_id = match.group(1)
            return self.video_id, None

        # Try direct CDN m3u8 URL
        if re.search(self.CDN_URL_PATTERN, self.url):
            self.video_id = "direct_m3u8"
            self.video_type = VimeoType.PUBLIC
            self.is_master_playlist = self._check_is_master_playlist()
            return self.video_id, None

        return None, None

    def _check_is_master_playlist(self) -> bool:
        """Check if URL is a master playlist (has audio) vs video-only component."""
        # Master playlists typically have these patterns
        if '/primary/' in self.url and 'playlist.m3u8' in self.url:
            return True
        # Video-only components have these patterns
        if 'st=video' in self.url or 'media.m3u8' in self.url:
            if '/primary/' not in self.url:
                return False
        return True  # Assume master if unsure

    def is_video_only_stream(self) -> bool:
        """Returns True if this appears to be a video-only stream URL."""
        if not hasattr(self, 'is_master_playlist'):
            self._check_is_master_playlist()
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
