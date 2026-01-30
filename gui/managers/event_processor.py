"""
Thread-safe event processing for GUI updates.
"""

import queue
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Callable


class EventType(Enum):
    """Types of GUI events."""
    PROGRESS_UPDATE = "progress_update"
    STATUS_CHANGE = "status_change"
    ANALYSIS_COMPLETE = "analysis_complete"
    DOWNLOAD_COMPLETE = "download_complete"
    DOWNLOAD_ERROR = "download_error"
    TITLE_UPDATE = "title_update"


@dataclass
class GUIEvent:
    """Event to be processed by the GUI."""
    event_type: EventType
    item_id: str
    data: Any = None


class EventProcessor:
    """
    Thread-safe event queue for communicating between worker threads and GUI.

    Worker threads push events to the queue, and the GUI polls for updates.
    """

    def __init__(self):
        self._queue = queue.Queue()
        self._handlers: dict[EventType, list[Callable]] = {}

    def push_event(self, event: GUIEvent) -> None:
        """Push an event to the queue (called from worker threads)."""
        self._queue.put(event)

    def push(self, event_type: EventType, item_id: str, data: Any = None) -> None:
        """Convenience method to push an event."""
        self.push_event(GUIEvent(event_type, item_id, data))

    def register_handler(self, event_type: EventType, handler: Callable) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def process_pending(self, max_events: int = 50) -> int:
        """
        Process pending events from the queue.

        Args:
            max_events: Maximum number of events to process in one call

        Returns:
            Number of events processed
        """
        processed = 0
        while processed < max_events:
            try:
                event = self._queue.get_nowait()
                self._dispatch_event(event)
                processed += 1
            except queue.Empty:
                break
        return processed

    def _dispatch_event(self, event: GUIEvent) -> None:
        """Dispatch an event to its registered handlers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Error in event handler: {e}")

    def clear(self) -> None:
        """Clear all pending events."""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
