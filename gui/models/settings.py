"""
Application settings with persistence.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class AppSettings:
    """Application settings that persist between sessions."""

    output_folder: str = "."
    temp_folder: str = ".downloading"
    quality_cap_1080p: bool = False
    fast_mode: bool = False
    use_aria2: bool = False
    no_cookies: bool = False
    browser: str = "chrome"
    browser_profile: Optional[str] = None
    window_width: int = 900
    window_height: int = 600
    theme: str = "dark"

    _settings_file: str = field(default="settings.json", repr=False)

    @classmethod
    def load(cls, settings_path: Optional[str] = None) -> "AppSettings":
        """Load settings from JSON file."""
        path = Path(settings_path) if settings_path else Path("settings.json")

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Filter out unknown keys and _settings_file
                valid_keys = {f.name for f in cls.__dataclass_fields__.values()
                             if not f.name.startswith("_")}
                filtered = {k: v for k, v in data.items() if k in valid_keys}
                settings = cls(**filtered)
                settings._settings_file = str(path)
                return settings
            except (json.JSONDecodeError, TypeError):
                pass

        settings = cls()
        settings._settings_file = str(path)
        return settings

    def save(self) -> None:
        """Save settings to JSON file."""
        path = Path(self._settings_file)
        data = {k: v for k, v in asdict(self).items() if not k.startswith("_")}

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_format_string(self) -> str:
        """Get yt-dlp format string based on quality settings."""
        if self.quality_cap_1080p:
            return "bv*[height<=1080]+ba/b[height<=1080]"
        return "bv*+ba/b"
