"""
URL input widget with batch file support.
"""

import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Optional


class URLInput(ctk.CTkFrame):
    """
    URL input widget with entry field and batch file button.
    """

    def __init__(
        self,
        master,
        on_url_submit: Callable[[str], None],
        on_batch_file: Callable[[str], None],
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self._on_url_submit = on_url_submit
        self._on_batch_file = on_batch_file

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        # URL entry
        self.url_entry = ctk.CTkEntry(
            self,
            placeholder_text="Enter video URL...",
            height=36,
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.url_entry.bind("<Return>", self._on_entry_submit)

        # Add button
        self.add_button = ctk.CTkButton(
            self,
            text="+ Add",
            width=70,
            height=36,
            command=self._on_add_clicked,
        )
        self.add_button.pack(side="left", padx=(0, 8))

        # Batch file button
        self.batch_button = ctk.CTkButton(
            self,
            text="Batch File",
            width=90,
            height=36,
            fg_color="gray40",
            hover_color="gray50",
            command=self._on_batch_clicked,
        )
        self.batch_button.pack(side="left")

    def _on_entry_submit(self, event=None) -> None:
        """Handle Enter key in entry."""
        self._on_add_clicked()

    def _on_add_clicked(self) -> None:
        """Handle Add button click."""
        url = self.url_entry.get().strip()
        if url:
            self._on_url_submit(url)
            self.url_entry.delete(0, "end")

    def _on_batch_clicked(self) -> None:
        """Handle Batch File button click."""
        filepath = filedialog.askopenfilename(
            title="Select Batch File",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if filepath:
            self._on_batch_file(filepath)

    def focus_entry(self) -> None:
        """Focus the URL entry field."""
        self.url_entry.focus_set()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the input."""
        state = "normal" if enabled else "disabled"
        self.url_entry.configure(state=state)
        self.add_button.configure(state=state)
        self.batch_button.configure(state=state)
