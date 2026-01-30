"""
Scrollable queue list widget.
"""

import customtkinter as ctk
from typing import Callable, Dict, Optional

from ..models.queue_item import QueueItem
from .queue_item_widget import QueueItemWidget


class QueueList(ctk.CTkScrollableFrame):
    """
    Scrollable list of queue items.
    """

    def __init__(
        self,
        master,
        on_item_remove: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self._on_item_remove = on_item_remove
        self._item_widgets: Dict[str, QueueItemWidget] = {}

        # Configure for vertical list layout
        self.grid_columnconfigure(0, weight=1)

    def add_item(self, item: QueueItem) -> None:
        """Add a queue item to the list."""
        if item.id in self._item_widgets:
            return

        widget = QueueItemWidget(
            self,
            item,
            on_remove=self._handle_item_remove,
        )
        widget.grid(row=len(self._item_widgets), column=0, sticky="ew", pady=(0, 4))
        self._item_widgets[item.id] = widget

    def update_item(self, item: QueueItem) -> None:
        """Update a queue item's display."""
        widget = self._item_widgets.get(item.id)
        if widget:
            widget.item = item
            widget.update_display()

    def remove_item(self, item_id: str) -> None:
        """Remove a queue item from the list."""
        widget = self._item_widgets.get(item_id)
        if widget:
            widget.destroy()
            del self._item_widgets[item_id]
            self._reflow_items()

    def clear(self) -> None:
        """Remove all items from the list."""
        for widget in self._item_widgets.values():
            widget.destroy()
        self._item_widgets.clear()

    def _reflow_items(self) -> None:
        """Reposition items after removal."""
        for i, widget in enumerate(self._item_widgets.values()):
            widget.grid(row=i, column=0, sticky="ew", pady=(0, 4))

    def _handle_item_remove(self, item_id: str) -> None:
        """Handle remove button click on an item."""
        if self._on_item_remove:
            self._on_item_remove(item_id)

    def get_item_count(self) -> int:
        """Get the number of items in the list."""
        return len(self._item_widgets)
