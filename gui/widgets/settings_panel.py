"""
Settings panel widget for download options.
"""

import customtkinter as ctk
from tkinter import filedialog
from typing import Callable

from ..models.settings import AppSettings


class SettingsPanel(ctk.CTkFrame):
    """
    Settings panel with output folder, quality, and download options.
    """

    def __init__(
        self,
        master,
        settings: AppSettings,
        on_settings_changed: Callable[[AppSettings], None],
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.settings = settings
        self._on_settings_changed = on_settings_changed

        self._setup_ui()
        self._load_from_settings()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        # Output folder section
        self._create_folder_section(
            "Output Folder:",
            "output_folder",
            row=0,
        )

        # Quality section
        self._create_quality_section(row=2)

        # Options section
        self._create_options_section(row=4)

        # Browser section
        self._create_browser_section(row=8)

    def _create_folder_section(self, label: str, setting_key: str, row: int) -> None:
        """Create a folder selection section."""
        label_widget = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        label_widget.grid(row=row, column=0, sticky="w", pady=(10, 2))

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row + 1, column=0, sticky="ew", pady=(0, 8))
        frame.grid_columnconfigure(0, weight=1)

        entry = ctk.CTkEntry(frame, height=28)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        browse_btn = ctk.CTkButton(
            frame,
            text="...",
            width=30,
            height=28,
            command=lambda: self._browse_folder(entry, setting_key),
        )
        browse_btn.grid(row=0, column=1)

        # Store reference
        setattr(self, f"_{setting_key}_entry", entry)

    def _create_quality_section(self, row: int) -> None:
        """Create quality selection section."""
        label = ctk.CTkLabel(
            self,
            text="Quality:",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        label.grid(row=row, column=0, sticky="w", pady=(10, 2))

        self._quality_var = ctk.StringVar(value="max")

        max_radio = ctk.CTkRadioButton(
            self,
            text="Max Quality",
            variable=self._quality_var,
            value="max",
            command=self._on_quality_changed,
        )
        max_radio.grid(row=row + 1, column=0, sticky="w", pady=2)

        cap_radio = ctk.CTkRadioButton(
            self,
            text="Cap at 1080p",
            variable=self._quality_var,
            value="1080p",
            command=self._on_quality_changed,
        )
        cap_radio.grid(row=row + 2, column=0, sticky="w", pady=2)

    def _create_options_section(self, row: int) -> None:
        """Create download options section."""
        label = ctk.CTkLabel(
            self,
            text="Options:",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        label.grid(row=row, column=0, sticky="w", pady=(10, 2))

        self._fast_var = ctk.BooleanVar()
        fast_check = ctk.CTkCheckBox(
            self,
            text="Fast mode (32 fragments)",
            variable=self._fast_var,
            command=self._on_option_changed,
        )
        fast_check.grid(row=row + 1, column=0, sticky="w", pady=2)

        self._aria2_var = ctk.BooleanVar()
        aria2_check = ctk.CTkCheckBox(
            self,
            text="Use aria2c",
            variable=self._aria2_var,
            command=self._on_option_changed,
        )
        aria2_check.grid(row=row + 2, column=0, sticky="w", pady=2)

        self._no_cookies_var = ctk.BooleanVar()
        cookies_check = ctk.CTkCheckBox(
            self,
            text="No cookies",
            variable=self._no_cookies_var,
            command=self._on_option_changed,
        )
        cookies_check.grid(row=row + 3, column=0, sticky="w", pady=2)

    def _create_browser_section(self, row: int) -> None:
        """Create browser selection section."""
        label = ctk.CTkLabel(
            self,
            text="Browser:",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        label.grid(row=row, column=0, sticky="w", pady=(10, 2))

        self._browser_var = ctk.StringVar(value="chrome")
        browser_menu = ctk.CTkOptionMenu(
            self,
            variable=self._browser_var,
            values=["chrome", "firefox", "edge"],
            command=self._on_browser_changed,
            width=150,
        )
        browser_menu.grid(row=row + 1, column=0, sticky="w", pady=2)

    def _browse_folder(self, entry: ctk.CTkEntry, setting_key: str) -> None:
        """Open folder browser dialog."""
        folder = filedialog.askdirectory(
            title=f"Select {setting_key.replace('_', ' ').title()}",
            initialdir=entry.get() or ".",
        )
        if folder:
            entry.delete(0, "end")
            entry.insert(0, folder)
            setattr(self.settings, setting_key, folder)
            self._notify_changed()

    def _on_quality_changed(self) -> None:
        """Handle quality selection change."""
        self.settings.quality_cap_1080p = self._quality_var.get() == "1080p"
        self._notify_changed()

    def _on_option_changed(self) -> None:
        """Handle option checkbox change."""
        self.settings.fast_mode = self._fast_var.get()
        self.settings.use_aria2 = self._aria2_var.get()
        self.settings.no_cookies = self._no_cookies_var.get()
        self._notify_changed()

    def _on_browser_changed(self, value: str) -> None:
        """Handle browser selection change."""
        self.settings.browser = value
        self._notify_changed()

    def _notify_changed(self) -> None:
        """Notify of settings change and save."""
        self.settings.save()
        self._on_settings_changed(self.settings)

    def _load_from_settings(self) -> None:
        """Load UI state from settings."""
        # Output folder
        self._output_folder_entry.delete(0, "end")
        self._output_folder_entry.insert(0, self.settings.output_folder)

        # Quality
        self._quality_var.set("1080p" if self.settings.quality_cap_1080p else "max")

        # Options
        self._fast_var.set(self.settings.fast_mode)
        self._aria2_var.set(self.settings.use_aria2)
        self._no_cookies_var.set(self.settings.no_cookies)

        # Browser
        self._browser_var.set(self.settings.browser)

    def get_settings(self) -> AppSettings:
        """Get current settings."""
        # Update settings from entry fields
        self.settings.output_folder = self._output_folder_entry.get() or "."
        return self.settings
