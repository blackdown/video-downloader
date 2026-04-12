"""
Browser cookie extraction and authentication handling.
"""

import os
import shutil
import tempfile
import sqlite3
import subprocess
import sys
import json
import base64
import ctypes
import ctypes.wintypes
from typing import Optional, Dict
from pathlib import Path

try:
    import browser_cookie3
    HAS_BROWSER_COOKIE3 = True
except ImportError:
    HAS_BROWSER_COOKIE3 = False


def _dpapi_decrypt(data: bytes) -> bytes:
    """Decrypt data using Windows DPAPI (no pywin32 required)."""
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', ctypes.wintypes.DWORD),
                    ('pbData', ctypes.POINTER(ctypes.c_char))]
    p = ctypes.create_string_buffer(data, len(data))
    blobin = DATA_BLOB(len(data), p)
    blobout = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout)):
        raise ctypes.WinError()
    result = ctypes.string_at(blobout.pbData, blobout.cbData)
    ctypes.windll.kernel32.LocalFree(blobout.pbData)
    return result


def extract_detection_profile_cookies(domain: Optional[str] = None) -> Dict[str, str]:
    """
    Extract cookies directly from the dedicated detection profile.
    Works even when Chrome is running (uses a temp copy of the DB).
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        print("Warning: cryptography package not installed, cannot extract detection profile cookies")
        return {}

    try:
        from core.browser_detect import get_detection_profile_dir, is_detection_profile_setup
    except ImportError:
        try:
            from .browser_detect import get_detection_profile_dir, is_detection_profile_setup
        except ImportError:
            return {}

    if not is_detection_profile_setup():
        print(f"[Cookies] Detection profile not set up yet")
        return {}

    profile_dir = get_detection_profile_dir()
    print(f"[Cookies] Extracting from detection profile for domain: {domain}")
    local_state_path = profile_dir / 'Local State'

    # Chrome stores cookies in Default/Cookies or Default/Network/Cookies
    cookies_candidates = [
        profile_dir / 'Default' / 'Network' / 'Cookies',
        profile_dir / 'Default' / 'Cookies',
    ]
    cookies_path = next((p for p in cookies_candidates if p.exists()), None)

    if not local_state_path.exists() or not cookies_path:
        print(f"[Cookies] Detection profile cookies not found at {profile_dir}")
        return {}

    try:
        # Get AES key from Local State (encrypted with DPAPI)
        with open(local_state_path, encoding='utf-8') as f:
            local_state = json.load(f)
        encrypted_key_b64 = local_state.get('os_crypt', {}).get('encrypted_key', '')
        if not encrypted_key_b64:
            return {}
        encrypted_key = base64.b64decode(encrypted_key_b64)
        # First 5 bytes are the literal "DPAPI" prefix
        aes_key = _dpapi_decrypt(encrypted_key[5:])

        # Copy DB to temp location to avoid SQLite lock conflicts
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tf:
            temp_db = tf.name
        shutil.copy2(str(cookies_path), temp_db)

        cookies: Dict[str, str] = {}
        total = matched = decrypted = 0
        last_err = None
        try:
            conn = sqlite3.connect(f'file:{temp_db}?mode=ro', uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT host_key, name, encrypted_value FROM cookies")
            rows = cursor.fetchall()
            total = len(rows)
            for host, name, encrypted_value in rows:
                if domain:
                    cookie_host = host.lstrip('.')
                    if not (domain == cookie_host or domain.endswith('.' + cookie_host)):
                        continue
                matched += 1
                try:
                    ev = bytes(encrypted_value)
                    if ev[:3] in (b'v10', b'v11', b'v20'):
                        iv = ev[3:15]
                        payload = ev[15:]
                        value = AESGCM(aes_key).decrypt(iv, payload, None).decode('utf-8')
                    elif os.name == 'nt' and ev:
                        value = _dpapi_decrypt(ev).decode('utf-8')
                    else:
                        continue
                    cookies[name] = value
                    decrypted += 1
                except Exception as e:
                    last_err = e
                    continue
            conn.close()
        finally:
            try:
                os.unlink(temp_db)
            except Exception:
                pass

        print(f"[Cookies] DB: {total} total, {matched} matched domain, {decrypted} decrypted" +
              (f" (last decrypt error: {last_err})" if last_err and decrypted == 0 else ""))
        return cookies

    except Exception as e:
        print(f"[Cookies] Detection profile extraction failed: {e}")
        return {}


def write_cookies_to_netscape_file(cookies: Dict[str, str], domain: str) -> Optional[str]:
    """Write cookies dict to a Netscape-format temp file for yt-dlp --cookies."""
    if not cookies:
        return None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("# Netscape HTTP Cookie File\n")
            for name, value in cookies.items():
                # domain  include_subdomains  path  secure  expiry  name  value
                f.write(f".{domain}\tTRUE\t/\tTRUE\t2147483647\t{name}\t{value}\n")
            return f.name
    except Exception as e:
        print(f"[Cookies] Failed to write cookies file: {e}")
        return None


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

        # Last resort: try the dedicated detection profile
        if domain:
            cookies = extract_detection_profile_cookies(domain)
            if cookies:
                self._cookies = cookies
                return cookies

        print("Warning: Could not extract cookies")
        return {}

    def get_detection_profile_cookies_file(self, domain: str) -> Optional[str]:
        """
        Write detection profile cookies for a domain to a temp Netscape cookies file.
        Returns the file path (caller is responsible for cleanup), or None if unavailable.
        """
        cookies = extract_detection_profile_cookies(domain)
        if not cookies:
            return None
        return write_cookies_to_netscape_file(cookies, domain)

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
                sys.executable, "-m", "yt_dlp",
                "--cookies-from-browser", browser_arg,
                "--cookies", cookie_file,
                "--skip-download",
                "--no-warnings",
                "--ignore-errors",
                "-q",
                target_url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            # Check for common errors
            if result.stderr:
                if "Could not copy" in result.stderr and "cookie database" in result.stderr:
                    print(f"Warning: Cannot access {self.browser} cookies - browser may be running. Close it and try again.")
                    return {}

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
            error_msg = str(e)
            if "Could not copy" in error_msg and "cookie database" in error_msg:
                print(f"Warning: Cannot access browser cookies - browser may be running. Close {self.browser} and try again.")
            else:
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
        if self.browser == "chrome":
            profile = self.get_chrome_profile_number()
            if profile:
                return f"chrome:{profile}"
            return "chrome"
        elif self.browser == "firefox":
            # Firefox doesn't need profile specification for default profile
            return "firefox"
        elif self.browser == "edge":
            return "edge"
        else:
            return self.browser
