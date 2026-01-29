"""
Browser cookie extraction and authentication handling.
"""

import browser_cookie3
import os
from typing import Optional, Dict
from pathlib import Path


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
    
    def extract_cookies(self) -> Optional[Dict]:
        """Extract cookies from browser."""
        try:
            if self.browser == "chrome":
                cookie_jar = browser_cookie3.chrome(domain_name='vimeo.com')
            elif self.browser == "firefox":
                cookie_jar = browser_cookie3.firefox(domain_name='vimeo.com')
            elif self.browser == "edge":
                cookie_jar = browser_cookie3.edge(domain_name='vimeo.com')
            else:
                return None
            
            # Convert to dict
            cookies = {}
            for cookie in cookie_jar:
                cookies[cookie.name] = cookie.value
            
            self._cookies = cookies
            return cookies
            
        except Exception as e:
            print(f"Warning: Could not extract cookies: {e}")
            return None
    
    def get_cookie_string_for_ytdlp(self) -> str:
        """Get the cookie browser string for yt-dlp --cookies-from-browser flag."""
        profile = self.get_chrome_profile_number()
        if profile:
            return f"chrome:{profile}"
        return "chrome"
