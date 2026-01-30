"""
Queue state management for the GUI.
"""

from typing import Dict, List, Optional, Callable
from pathlib import Path

from ..models.queue_item import QueueItem, QueueStatus
from ..models.settings import AppSettings
from .download_worker import DownloadWorker
from .event_processor import EventProcessor, EventType, GUIEvent


class QueueManager:
    """
    Manages the download queue state and orchestrates workers.
    """

    def __init__(self, settings: AppSettings, event_processor: EventProcessor):
        self.settings = settings
        self.events = event_processor

        self._items: Dict[str, QueueItem] = {}
        self._workers: Dict[str, DownloadWorker] = {}
        self._order: List[str] = []  # Maintains insertion order

        self._is_running = False
        self._max_concurrent = 1  # Download one at a time for now

        # Register event handlers
        self.events.register_handler(EventType.STATUS_CHANGE, self._on_status_change)
        self.events.register_handler(EventType.PROGRESS_UPDATE, self._on_progress_update)
        self.events.register_handler(EventType.ANALYSIS_COMPLETE, self._on_analysis_complete)
        self.events.register_handler(EventType.DOWNLOAD_COMPLETE, self._on_download_complete)
        self.events.register_handler(EventType.DOWNLOAD_ERROR, self._on_download_error)

        # Callbacks for UI updates
        self._on_item_updated: Optional[Callable[[QueueItem], None]] = None

    def set_item_updated_callback(self, callback: Callable[[QueueItem], None]) -> None:
        """Set callback to be called when an item is updated."""
        self._on_item_updated = callback

    def add_url(self, url: str) -> QueueItem:
        """Add a URL to the queue."""
        url = url.strip()
        if not url:
            raise ValueError("URL cannot be empty")

        item = QueueItem(url=url)
        self._items[item.id] = item
        self._order.append(item.id)

        return item

    def add_urls(self, urls: List[str]) -> List[QueueItem]:
        """Add multiple URLs to the queue."""
        items = []
        for url in urls:
            url = url.strip()
            if url and not url.startswith("#"):
                items.append(self.add_url(url))
        return items

    def load_batch_file(self, path: str) -> List[QueueItem]:
        """Load URLs from a batch file."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Batch file not found: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        return self.add_urls(urls)

    def remove_item(self, item_id: str) -> None:
        """Remove an item from the queue."""
        if item_id in self._workers:
            self._workers[item_id].cancel()
            del self._workers[item_id]

        if item_id in self._items:
            del self._items[item_id]

        if item_id in self._order:
            self._order.remove(item_id)

    def get_item(self, item_id: str) -> Optional[QueueItem]:
        """Get an item by ID."""
        return self._items.get(item_id)

    def get_all_items(self) -> List[QueueItem]:
        """Get all items in order."""
        return [self._items[id] for id in self._order if id in self._items]

    def start(self) -> None:
        """Start processing the queue."""
        self._is_running = True
        self._start_next_downloads()

    def pause(self) -> None:
        """Pause queue processing (finish current downloads but don't start new ones)."""
        self._is_running = False

    def cancel_all(self) -> None:
        """Cancel all active downloads."""
        for worker in self._workers.values():
            worker.cancel()
        self._is_running = False

    def clear_completed(self) -> None:
        """Remove completed and error items from the queue."""
        to_remove = [
            item_id for item_id, item in self._items.items()
            if item.status in (QueueStatus.COMPLETED, QueueStatus.ERROR, QueueStatus.CANCELLED)
        ]
        for item_id in to_remove:
            self.remove_item(item_id)

    def get_stats(self) -> dict:
        """Get queue statistics."""
        statuses = [item.status for item in self._items.values()]
        return {
            "total": len(self._items),
            "pending": statuses.count(QueueStatus.PENDING),
            "analyzing": statuses.count(QueueStatus.ANALYZING),
            "downloading": statuses.count(QueueStatus.DOWNLOADING),
            "completed": statuses.count(QueueStatus.COMPLETED),
            "error": statuses.count(QueueStatus.ERROR),
        }

    def _start_next_downloads(self) -> None:
        """Start the next pending downloads if capacity allows."""
        if not self._is_running:
            return

        active_count = sum(1 for w in self._workers.values() if w.is_running())
        available_slots = self._max_concurrent - active_count

        if available_slots <= 0:
            return

        # Find pending items
        for item_id in self._order:
            if available_slots <= 0:
                break

            item = self._items.get(item_id)
            if item and item.status == QueueStatus.PENDING:
                self._start_download(item)
                available_slots -= 1

    def _start_download(self, item: QueueItem) -> None:
        """Start downloading a specific item."""
        worker = DownloadWorker(item, self.settings, self.events)
        self._workers[item.id] = worker
        worker.start()

    def _notify_item_updated(self, item: QueueItem) -> None:
        """Notify UI of item update."""
        if self._on_item_updated:
            self._on_item_updated(item)

    # Event handlers
    def _on_status_change(self, event: GUIEvent) -> None:
        """Handle status change event."""
        item = self._items.get(event.item_id)
        if item:
            item.status = event.data
            self._notify_item_updated(item)

            # If completed/error/cancelled, try to start next download
            if event.data in (QueueStatus.COMPLETED, QueueStatus.ERROR, QueueStatus.CANCELLED):
                self._start_next_downloads()

    def _on_progress_update(self, event: GUIEvent) -> None:
        """Handle progress update event."""
        item = self._items.get(event.item_id)
        if item and isinstance(event.data, dict):
            item.progress = event.data.get("percent", 0)
            item.speed = event.data.get("speed", "")
            item.eta = event.data.get("eta", "")
            self._notify_item_updated(item)

    def _on_analysis_complete(self, event: GUIEvent) -> None:
        """Handle analysis complete event."""
        item = self._items.get(event.item_id)
        if item and isinstance(event.data, dict):
            item.platform = event.data.get("platform")
            item.is_video_only = event.data.get("is_video_only", False)
            if event.data.get("title"):
                item.title = event.data["title"]
            self._notify_item_updated(item)

    def _on_download_complete(self, event: GUIEvent) -> None:
        """Handle download complete event."""
        item = self._items.get(event.item_id)
        if item:
            item.status = QueueStatus.COMPLETED
            item.progress = 100.0
            self._notify_item_updated(item)
            self._start_next_downloads()

    def _on_download_error(self, event: GUIEvent) -> None:
        """Handle download error event."""
        item = self._items.get(event.item_id)
        if item:
            item.status = QueueStatus.ERROR
            item.error_message = str(event.data) if event.data else "Unknown error"
            self._notify_item_updated(item)
            self._start_next_downloads()
