"""
Browser cookie extraction and authentication handling.
"""

import os
import shutil
import tempfile
import sqlite3
import subprocess
import json
from typing import Optional, Dict
from pathlib import Path

from .runtime import ytdlp_cmd, ffmpeg_env

try:
    import browser_cookie3
    HAS_BROWSER_COOKIE3 = True
except ImportError:
    HAS_BROWSER_COOKIE3 = False


class CookieManager:
    """Manage browser cookies for Vimeo authentication."""
    
    def __init__(self, browser: str = "chrome", profile: Optional[str] = None):
        self.browser = browser.lower()
        self.profile = profile
        self._cookies = None
        
    def get_chrome_profile_number(self) -> Optional[str]:
        """
        Auto-detect Chrome profile number.
        Returns the profile name (e.g., 'Profile 1', 'Default').
        """
        if self.profile:
            return self.profile
            
        # Try to find Chrome user data directory
        if os.name == 'nt':  # Windows
            base_path = Path(os.environ.get('LOCALAPPDATA', '')) / 'Google' / 'Chrome' / 'User Data'
        elif os.name == 'posix':
            import sys
            if 'darwin' in sys.platform:  # macOS
                base_path = Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome'
            else:  # Linux
                base_path = Path.home() / '.config' / 'google-chrome'
        else:
            return None
        
        # Check for profiles
        if not base_path.exists():
            return None
            
        # Look for Default first, then Profile directories
        if (base_path / 'Default').exists():
            return 'Default'
        
        # Find numbered profiles
        for i in range(1, 20):
            profile_path = base_path / f'Profile {i}'
            if profile_path.exists():
                return f'Profile {i}'
        
        return None
    
    def extract_cookies(self, domain: Optional[str] = None) -> Optional[Dict]:
        """Extract cookies from browser.

        Args:
            domain: Optional domain to filter cookies. If None, gets all cookies.
        """
        # Try yt-dlp extraction first (most reliable on Windows)
        cookies = self._extract_with_ytdlp(domain)
        if cookies:
            self._cookies = cookies
            return cookies

        # Fall back to browser_cookie3
        if HAS_BROWSER_COOKIE3:
            cookies = self._extract_with_browser_cookie3(domain)
            if cookies:
                self._cookies = cookies
                return cookies

        print("Warning: Could not extract cookies")
        return {}

    def _extract_with_ytdlp(self, domain: Optional[str] = None) -> Dict:
        """Extract cookies using yt-dlp (handles Chrome encryption on Windows)."""
        try:
            # Create a temp file for cookies
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                cookie_file = f.name

            # Use yt-dlp to export cookies to Netscape format
            browser_arg = self.browser
            if self.profile:
                browser_arg = f"{self.browser}:{self.profile}"

            # Use the target domain URL so yt-dlp exports the right cookies
            target_url = f"https://{domain}/" if domain else "https://example.com"

            cmd = [
                *ytdlp_cmd(),
                "--cookies-from-browser", browser_arg,
                "--cookies", cookie_file,
                "--skip-download",
                "--no-warnings",
                "--ignore-errors",
                "-q",
                target_url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=ffmpeg_env())

            # Parse the Netscape cookie file
            cookies = {}
            if os.path.exists(cookie_file):
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = line.split('\t')
                        if len(parts) >= 7:
                            cookie_domain = parts[0]
                            name = parts[5]
                            value = parts[6]
                            # Filter by domain if specified
                            if domain is None or domain in cookie_domain:
                                cookies[name] = value

                os.unlink(cookie_file)

            if cookies:
                print(f"Extracted {len(cookies)} cookies via yt-dlp")

            return cookies

        except Exception as e:
            print(f"Warning: yt-dlp cookie extraction failed: {e}")
            # Clean up temp file if it exists
            try:
                if 'cookie_file' in locals() and os.path.exists(cookie_file):
                    os.unlink(cookie_file)
            except:
                pass
            return {}

    def _extract_with_browser_cookie3(self, domain: Optional[str] = None) -> Dict:
        """Extract cookies using browser_cookie3 library."""
        try:
            if self.browser == "chrome":
                cookie_jar = browser_cookie3.chrome(domain_name=domain) if domain else browser_cookie3.chrome()
            elif self.browser == "firefox":
                cookie_jar = browser_cookie3.firefox(domain_name=domain) if domain else browser_cookie3.firefox()
            elif self.browser == "edge":
                cookie_jar = browser_cookie3.edge(domain_name=domain) if domain else browser_cookie3.edge()
            else:
                return {}

            # Convert to dict
            cookies = {}
            for cookie in cookie_jar:
                cookies[cookie.name] = cookie.value

            return cookies

        except Exception as e:
            print(f"Warning: browser_cookie3 extraction failed: {e}")
            return {}
    
    def get_cookie_string_for_ytdlp(self) -> str:
        """Get the cookie browser string for yt-dlp --cookies-from-browser flag."""
        profile = self.get_chrome_profile_number()
        if profile:
            return f"chrome:{profile}"
        return "chrome"
