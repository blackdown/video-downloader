"""
Main application window for the Video Downloader GUI.
"""

import customtkinter as ctk
from typing import Optional

from .models.queue_item import QueueItem, QueueStatus
from .models.settings import AppSettings
from .managers.queue_manager import QueueManager
from .managers.event_processor import EventProcessor
from .managers.logger import get_logger
from .widgets.url_input import URLInput
from .widgets.queue_list import QueueList
from .widgets.settings_panel import SettingsPanel
from .widgets.stream_warning import StreamWarning
from .widgets.log_viewer import LogViewer


class MainWindow(ctk.CTk):
    """
    Main application window.
    """

    def __init__(self):
        super().__init__()

        # Initialize logging first
        self.log = get_logger()
        self.log.info("MainWindow initializing")

        # Load settings
        self.settings = AppSettings.load()
        self.settings.use_aria2 = False  # aria2c doesn't work with network paths
        self.settings.no_cookies = True  # Cookie extraction adds complexity, not needed for most URLs
        self.log.info(f"Settings loaded: output={self.settings.output_folder}")

        # Set up window
        self.title("Video Downloader")
        self.geometry("900x600")  # Fixed size - DPI scaling breaks saved sizes
        self.minsize(700, 400)

        # Set appearance
        ctk.set_appearance_mode(self.settings.theme)
        ctk.set_default_color_theme("blue")

        # Initialize managers
        self.events = EventProcessor()
        self.queue_manager = QueueManager(self.settings, self.events)
        self.queue_manager.set_item_updated_callback(self._on_item_updated)

        # Track selected item for stream warning
        self._selected_item_id: Optional[str] = None

        # Log viewer window reference
        self._log_viewer: Optional[LogViewer] = None

        # Build UI
        self._setup_ui()

        # Start event polling
        self._poll_events()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.log.info("MainWindow initialization complete")

    def _setup_ui(self) -> None:
        """Set up the main UI layout."""
        # Configure grid
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1, minsize=220)
        self.grid_rowconfigure(1, weight=1)

        # URL input (top, spans both columns)
        self.url_input = URLInput(
            self,
            on_url_submit=self._on_url_add,
            on_batch_file=self._on_batch_file,
        )
        self.url_input.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))

        # Queue list (left side)
        queue_frame = ctk.CTkFrame(self)
        queue_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 8))
        queue_frame.grid_columnconfigure(0, weight=1)
        queue_frame.grid_rowconfigure(1, weight=1)

        queue_label = ctk.CTkLabel(
            queue_frame,
            text="Queue:",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        queue_label.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        self.queue_list = QueueList(
            queue_frame,
            on_item_remove=self._on_item_remove,
        )
        self.queue_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Control buttons (below queue)
        controls_frame = ctk.CTkFrame(queue_frame, fg_color="transparent")
        controls_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))

        self.start_button = ctk.CTkButton(
            controls_frame,
            text="Start",
            width=70,
            command=self._on_start,
            fg_color="#2d5a27",
            hover_color="#3d7a37",
        )
        self.start_button.pack(side="left", padx=(0, 4))

        self.pause_button = ctk.CTkButton(
            controls_frame,
            text="Pause",
            width=70,
            command=self._on_pause,
            fg_color="gray40",
            hover_color="gray50",
        )
        self.pause_button.pack(side="left", padx=(0, 4))

        self.cancel_button = ctk.CTkButton(
            controls_frame,
            text="Cancel",
            width=70,
            command=self._on_cancel,
            fg_color="#8b2500",
            hover_color="#ab3500",
        )
        self.cancel_button.pack(side="left", padx=(0, 4))

        self.clear_button = ctk.CTkButton(
            controls_frame,
            text="Clear Done",
            width=80,
            command=self._on_clear_done,
            fg_color="gray40",
            hover_color="gray50",
        )
        self.clear_button.pack(side="left")

        # Right panel (settings + stream warning)
        right_panel = ctk.CTkFrame(self)
        right_panel.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(6, 12), pady=12)
        right_panel.grid_columnconfigure(0, weight=1)

        self.settings_panel = SettingsPanel(
            right_panel,
            self.settings,
            on_settings_changed=self._on_settings_changed,
        )
        self.settings_panel.grid(row=0, column=0, sticky="new", padx=8, pady=8)

        # Stream warning indicator
        self.stream_warning = StreamWarning(right_panel)
        self.stream_warning.grid(row=1, column=0, sticky="new", padx=8, pady=(16, 8))

        # View Log button (at bottom of right panel)
        self.log_button = ctk.CTkButton(
            right_panel,
            text="View Log",
            width=100,
            fg_color="gray40",
            hover_color="gray50",
            command=self._on_view_log,
        )
        self.log_button.grid(row=2, column=0, sticky="s", padx=8, pady=(16, 8))

        # Status bar (bottom)
        self.status_bar = ctk.CTkLabel(
            self,
            text="Ready",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))

    def _poll_events(self) -> None:
        """Poll for GUI events from worker threads."""
        self.events.process_pending()
        self._update_status_bar()
        self.after(100, self._poll_events)  # Poll every 100ms

    def _update_status_bar(self) -> None:
        """Update the status bar with queue statistics."""
        stats = self.queue_manager.get_stats()

        if stats["downloading"] > 0:
            status = f"Downloading {stats['downloading']}/{stats['total']}"
        elif stats["analyzing"] > 0:
            status = f"Analyzing... ({stats['analyzing']} items)"
        elif stats.get("ready", 0) > 0:
            status = f"{stats['ready']} ready to download"
        elif stats["completed"] > 0:
            status = f"Completed: {stats['completed']}/{stats['total']}"
        elif stats["total"] > 0:
            status = f"{stats['total']} items in queue"
        else:
            status = "Ready"

        if stats["error"] > 0:
            status += f" | {stats['error']} errors"

        self.status_bar.configure(text=status)

    def _on_url_add(self, url: str, filename: Optional[str] = None) -> None:
        """Handle URL addition."""
        self.log.info(f"Adding URL: {url[:80]}" + (f" with filename: {filename}" if filename else ""))
        try:
            item = self.queue_manager.add_url(url, filename)
            self.queue_list.add_item(item)
            self._update_stream_warning(item)
        except ValueError as e:
            self.log.error(f"Error adding URL: {e}")
            self._show_error(str(e))

    def _on_batch_file(self, filepath: str) -> None:
        """Handle batch file selection."""
        self.log.info(f"Loading batch file: {filepath}")
        try:
            items = self.queue_manager.load_batch_file(filepath)
            for item in items:
                self.queue_list.add_item(item)
            self.log.info(f"Added {len(items)} items from batch file")
            self.status_bar.configure(text=f"Added {len(items)} items from batch file")
        except FileNotFoundError as e:
            self.log.error(f"Batch file error: {e}")
            self._show_error(str(e))

    def _on_item_remove(self, item_id: str) -> None:
        """Handle item removal."""
        self.log.info(f"Removing item: {item_id}")
        self.queue_manager.remove_item(item_id)
        self.queue_list.remove_item(item_id)

    def _on_item_updated(self, item: QueueItem) -> None:
        """Handle item update from worker."""
        self.queue_list.update_item(item)
        self._update_stream_warning(item)

    def _update_stream_warning(self, item: QueueItem) -> None:
        """Update stream warning indicator."""
        # Show warning for the most recently updated/selected item
        is_analyzed = item.platform is not None
        self.stream_warning.update_from_item(item.is_video_only, is_analyzed)

    def _on_start(self) -> None:
        """Handle Start button click."""
        self.log.info("Start button clicked")
        self.queue_manager.start()

    def _on_pause(self) -> None:
        """Handle Pause button click."""
        self.log.info("Pause button clicked")
        self.queue_manager.pause()

    def _on_cancel(self) -> None:
        """Handle Cancel button click."""
        self.log.info("Cancel button clicked")
        self.queue_manager.cancel_all()

    def _on_clear_done(self) -> None:
        """Handle Clear Done button click."""
        self.log.info("Clear Done button clicked")
        # Get IDs of completed items before clearing
        completed_ids = [
            item.id for item in self.queue_manager.get_all_items()
            if item.status in (QueueStatus.COMPLETED, QueueStatus.ERROR, QueueStatus.CANCELLED)
        ]

        # Clear from manager
        self.queue_manager.clear_completed()

        # Clear from UI
        for item_id in completed_ids:
            self.queue_list.remove_item(item_id)

    def _on_view_log(self) -> None:
        """Handle View Log button click."""
        self.log.info("Opening log viewer")
        # Create new log viewer or bring existing to front
        if self._log_viewer is None or not self._log_viewer.winfo_exists():
            from .managers.logger import _default_log_path
            self._log_viewer = LogViewer(self, log_file=_default_log_path())
        else:
            self._log_viewer.focus()
            self._log_viewer._load_log()  # Refresh

    def _on_settings_changed(self, settings: AppSettings) -> None:
        """Handle settings change."""
        self.log.info("Settings changed")
        self.settings = settings

    def _show_error(self, message: str) -> None:
        """Show an error message."""
        self.status_bar.configure(text=f"Error: {message}", text_color="#ff6666")
        self.after(3000, lambda: self.status_bar.configure(text_color="gray60"))

    def _on_close(self) -> None:
        """Handle window close."""
        self.log.info("Window closing")

        # Cancel any running downloads
        self.queue_manager.cancel_all()

        self.log.info("Application shutdown complete")
        self.destroy()
