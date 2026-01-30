"""
Log viewer dialog widget.
"""

import customtkinter as ctk
from pathlib import Path


class LogViewer(ctk.CTkToplevel):
    """
    Dialog window for viewing the log file.
    """

    def __init__(self, master, log_file: str = "video_dl_gui.log", **kwargs):
        super().__init__(master, **kwargs)

        self.log_file = log_file
        self.title("Log Viewer")
        self.geometry("800x500")
        self.minsize(600, 300)

        # Make it stay on top initially
        self.transient(master)

        self._setup_ui()
        self._load_log()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Text widget with scrollbar
        self.text_frame = ctk.CTkFrame(self)
        self.text_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        self.text_frame.grid_columnconfigure(0, weight=1)
        self.text_frame.grid_rowconfigure(0, weight=1)

        self.text_widget = ctk.CTkTextbox(
            self.text_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="none",
        )
        self.text_widget.grid(row=0, column=0, sticky="nsew")

        # Button frame
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 10))

        self.refresh_button = ctk.CTkButton(
            button_frame,
            text="Refresh",
            width=100,
            command=self._load_log,
        )
        self.refresh_button.pack(side="left", padx=(0, 5))

        self.scroll_bottom_button = ctk.CTkButton(
            button_frame,
            text="Scroll to Bottom",
            width=120,
            command=self._scroll_to_bottom,
        )
        self.scroll_bottom_button.pack(side="left", padx=(0, 5))

        self.clear_button = ctk.CTkButton(
            button_frame,
            text="Clear Log",
            width=100,
            fg_color="gray40",
            hover_color="gray50",
            command=self._clear_log,
        )
        self.clear_button.pack(side="left", padx=(0, 5))

        self.close_button = ctk.CTkButton(
            button_frame,
            text="Close",
            width=80,
            fg_color="gray40",
            hover_color="gray50",
            command=self.destroy,
        )
        self.close_button.pack(side="right")

        # Log file path label
        self.path_label = ctk.CTkLabel(
            button_frame,
            text=f"Log file: {self.log_file}",
            font=ctk.CTkFont(size=10),
            text_color="gray60",
        )
        self.path_label.pack(side="left", padx=(20, 0))

    def _load_log(self) -> None:
        """Load and display the log file contents."""
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")

        path = Path(self.log_file)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.text_widget.insert("1.0", content)
            except Exception as e:
                self.text_widget.insert("1.0", f"Error reading log file: {e}")
        else:
            self.text_widget.insert("1.0", "Log file not found. Start a download to create it.")

        self.text_widget.configure(state="disabled")
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the log."""
        self.text_widget.see("end")

    def _clear_log(self) -> None:
        """Clear the log file."""
        path = Path(self.log_file)
        if path.exists():
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("")
                self._load_log()
            except Exception as e:
                self.text_widget.configure(state="normal")
                self.text_widget.delete("1.0", "end")
                self.text_widget.insert("1.0", f"Error clearing log file: {e}")
                self.text_widget.configure(state="disabled")
