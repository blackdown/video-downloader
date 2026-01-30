"""
Individual queue item widget for display in the queue list.
"""

import customtkinter as ctk
from typing import Callable, Optional

from ..models.queue_item import QueueItem, QueueStatus


class QueueItemWidget(ctk.CTkFrame):
    """
    Widget displaying a single queue item with progress.
    """

    # Status colors
    STATUS_COLORS = {
        QueueStatus.PENDING: "gray50",
        QueueStatus.ANALYZING: "#4a90d9",  # Blue
        QueueStatus.READY: "#2d5a27",  # Green - ready to download
        QueueStatus.DOWNLOADING: "#4a90d9",  # Blue
        QueueStatus.COMPLETED: "#2d5a27",  # Green
        QueueStatus.ERROR: "#8b2500",  # Red
        QueueStatus.CANCELLED: "gray50",
        QueueStatus.PAUSED: "#8a7a00",  # Yellow
    }

    def __init__(
        self,
        master,
        item: QueueItem,
        on_remove: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(master, corner_radius=6, **kwargs)

        self.item = item
        self._on_remove = on_remove

        self._setup_ui()
        self.update_display()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.grid_columnconfigure(1, weight=1)

        # Platform badge
        self.platform_label = ctk.CTkLabel(
            self,
            text="??",
            width=45,
            height=24,
            corner_radius=4,
            fg_color="gray40",
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.platform_label.grid(row=0, column=0, padx=(8, 8), pady=8)

        # Title/URL
        self.title_label = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=12),
        )
        self.title_label.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 0))

        # Status label
        self.status_label = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=10),
            text_color="gray60",
        )
        self.status_label.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 2))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=8,
            corner_radius=4,
        )
        self.progress_bar.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))
        self.progress_bar.set(0)

        # Remove button
        self.remove_button = ctk.CTkButton(
            self,
            text="X",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="gray40",
            text_color="gray60",
            font=ctk.CTkFont(size=12),
            command=self._on_remove_clicked,
        )
        self.remove_button.grid(row=0, column=2, rowspan=3, padx=(0, 8))

    def update_display(self) -> None:
        """Update the widget display from the item state."""
        # Platform badge
        platform_text = self.item.get_platform_short()
        self.platform_label.configure(text=platform_text)

        # Set platform badge color
        platform_colors = {
            "YT": "#ff0000",  # YouTube red
            "VM": "#1ab7ea",  # Vimeo blue
            "KS": "#6b5b95",  # Kinescope purple
            "GC": "#ff6600",  # GetCourse orange
            "M3U8": "#333333",  # Direct stream gray
        }
        badge_color = platform_colors.get(platform_text, "gray40")
        self.platform_label.configure(fg_color=badge_color)

        # Title
        self.title_label.configure(text=self.item.get_display_title(50))

        # Status text
        status_text = self.item.get_status_display()
        if self.item.status == QueueStatus.DOWNLOADING:
            if self.item.speed:
                status_text += f" | {self.item.speed}"
            if self.item.eta:
                status_text += f" | ETA: {self.item.eta}"
        elif self.item.status == QueueStatus.ERROR and self.item.error_message:
            status_text += f": {self.item.error_message[:40]}"

        self.status_label.configure(text=status_text)

        # Progress bar
        progress_value = self.item.progress / 100.0
        self.progress_bar.set(progress_value)

        # Progress bar color based on status
        status_color = self.STATUS_COLORS.get(self.item.status, "gray50")
        self.progress_bar.configure(progress_color=status_color)

        # Show/hide progress bar based on status
        if self.item.status in (QueueStatus.PENDING, QueueStatus.CANCELLED):
            self.progress_bar.grid_remove()
        else:
            self.progress_bar.grid()

        # Video-only warning indicator
        if self.item.is_video_only and self.item.platform:
            self.title_label.configure(text_color="#d4a700")  # Yellow text
        else:
            self.title_label.configure(text_color=("gray10", "gray90"))

    def _on_remove_clicked(self) -> None:
        """Handle remove button click."""
        if self._on_remove:
            self._on_remove(self.item.id)
