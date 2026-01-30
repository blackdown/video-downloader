"""
Queue item dataclass for tracking download status.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class QueueStatus(Enum):
    """Status of a queue item."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class QueueItem:
    """Represents a single item in the download queue."""

    url: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: QueueStatus = QueueStatus.PENDING
    title: Optional[str] = None
    platform: Optional[str] = None  # YT, VM, KS, etc.
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    error_message: Optional[str] = None
    is_video_only: bool = False
    output_path: Optional[str] = None

    def get_platform_short(self) -> str:
        """Get short platform identifier for display."""
        platform_map = {
            "youtube": "YT",
            "vimeo": "VM",
            "kinescope": "KS",
            "getcourse": "GC",
            "direct_stream": "M3U8",
        }
        if self.platform:
            return platform_map.get(self.platform.lower(), "??")
        return "??"

    def get_status_display(self) -> str:
        """Get human-readable status string."""
        status_map = {
            QueueStatus.PENDING: "Waiting",
            QueueStatus.ANALYZING: "Analyzing...",
            QueueStatus.DOWNLOADING: "Downloading",
            QueueStatus.COMPLETED: "Completed",
            QueueStatus.ERROR: "Error",
            QueueStatus.CANCELLED: "Cancelled",
            QueueStatus.PAUSED: "Paused",
        }
        return status_map.get(self.status, "Unknown")

    def get_display_title(self, max_length: int = 40) -> str:
        """Get title for display, truncated if needed."""
        title = self.title or self.url
        if len(title) > max_length:
            return title[:max_length - 3] + "..."
        return title
