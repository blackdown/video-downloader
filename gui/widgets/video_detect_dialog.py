"""
Dialog for browser-based video detection.
"""

import customtkinter as ctk
from typing import Callable, List, Optional
from dataclasses import dataclass

from ..managers.logger import get_logger


@dataclass
class VideoResult:
    """Result from video detection."""
    url: str
    source: str
    title: Optional[str] = None
    selected: bool = True


class VideoDetectDialog(ctk.CTkToplevel):
    """
    Dialog for detecting videos from a webpage using browser automation.
    """

    def __init__(
        self,
        master,
        on_add_videos: Callable[[List[str]], None],
        browser: str = "chrome",
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_add_videos = on_add_videos
        self.browser = browser
        self._detected_videos: List[VideoResult] = []
        self._checkboxes: List[tuple] = []  # (checkbox, var, video)
        self._detection_thread = None
        self.log = get_logger()

        # Window setup
        self.title("Detect Videos from Page")
        self.geometry("600x450")
        self.minsize(500, 350)

        # Make modal
        self.transient(master)
        self.grab_set()

        self._setup_ui()
        self.focus()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # URL input section
        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        input_frame.grid_columnconfigure(0, weight=1)

        # Header with browser info
        header_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            header_frame,
            text="Enter page URL (e.g., Skillshare class page)",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

        ctk.CTkLabel(
            header_frame,
            text="Uses dedicated browser profile",
            font=ctk.CTkFont(size=11),
            text_color="#6b5b95",
        ).pack(side="right")

        self.url_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="https://example.com/video-page",
            height=36,
        )
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=(0, 8))
        self.url_entry.bind("<Return>", lambda e: self._on_detect())

        self.detect_button = ctk.CTkButton(
            input_frame,
            text="Detect",
            width=80,
            height=36,
            command=self._on_detect,
        )
        self.detect_button.grid(row=1, column=1, padx=(0, 8), pady=(0, 8))

        # Status label
        self.status_label = ctk.CTkLabel(
            self,
            text="Enter a URL and click Detect to find videos on the page.",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self.status_label.grid(row=1, column=0, sticky="w", padx=24, pady=(0, 8))

        # Results section (scrollable)
        results_frame = ctk.CTkFrame(self)
        results_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)

        self.results_scroll = ctk.CTkScrollableFrame(results_frame)
        self.results_scroll.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.results_scroll.grid_columnconfigure(0, weight=1)

        # Bottom buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))

        self.select_all_button = ctk.CTkButton(
            button_frame,
            text="Select All",
            width=90,
            fg_color="gray40",
            hover_color="gray50",
            command=self._on_select_all,
            state="disabled",
        )
        self.select_all_button.pack(side="left", padx=(0, 8))

        self.add_button = ctk.CTkButton(
            button_frame,
            text="Add to Queue",
            width=120,
            fg_color="#2d5a27",
            hover_color="#3d7a37",
            command=self._on_add_to_queue,
            state="disabled",
        )
        self.add_button.pack(side="left")

        self.cancel_button = ctk.CTkButton(
            button_frame,
            text="Close",
            width=80,
            fg_color="gray40",
            hover_color="gray50",
            command=self.destroy,
        )
        self.cancel_button.pack(side="right")

        # Now create the placeholder (after buttons exist)
        self._update_placeholder()

    def _on_detect(self) -> None:
        """Start video detection."""
        url = ''.join(self.url_entry.get().split())
        if not url:
            self._set_status("Please enter a URL", error=True)
            return

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)

        self.log.info(f"[Detect] Starting detection for: {url[:80]}...")
        self.log.info(f"[Detect] Using browser: {self.browser}")

        # Check if Playwright is available
        try:
            from core.browser_detect import is_playwright_available, detect_videos_async
            if not is_playwright_available():
                msg = "Playwright not installed. Run: pip install playwright && playwright install chromium"
                self.log.error(f"[Detect] {msg}")
                self._set_status(msg, error=True)
                return
        except ImportError as e:
            self.log.error(f"[Detect] Import error: {e}")
            self._set_status(f"Import error: {e}", error=True)
            return

        # Clear previous results
        self._clear_results()

        # Disable detect button during detection
        self.detect_button.configure(state="disabled", text="Detecting...")
        self._set_status("Launching browser...")

        # Start detection in background
        from core.browser_detect import detect_videos_async

        self._detection_thread = detect_videos_async(
            url=url,
            browser=self.browser,
            headless=False,  # Need visible browser for auth
            timeout=15000,
            on_complete=self._on_detection_complete,
            on_progress=self._on_detection_progress,
            on_video_found=self._on_video_found,
        )

    def _on_detection_progress(self, message: str) -> None:
        """Handle progress update from detection thread."""
        self.log.debug(f"[Detect] {message}")
        # Schedule UI update on main thread
        self.after(0, lambda: self._set_status(message))

    def _on_video_found(self, video) -> None:
        """Handle a video being found - add to UI immediately."""
        # Schedule UI update on main thread
        self.after(0, lambda: self._add_video_to_list(video))

    def _on_detection_complete(self, videos: list, error: Optional[str]) -> None:
        """Handle detection completion."""
        # Schedule UI update on main thread
        self.after(0, lambda: self._finish_detection(error))

    def _add_video_to_list(self, video) -> None:
        """Add a single video to the results list (real-time update)."""
        # Only add master playlists (with audio)
        if not video.is_master:
            return

        # Hide placeholder if this is the first video
        if not self._detected_videos:
            self.placeholder_label.grid_remove()
            self.select_all_button.configure(state="normal")
            self.add_button.configure(state="normal")

        result = VideoResult(
            url=video.url,
            source=video.source,
            title=video.title,
            selected=True,
        )
        self._detected_videos.append(result)

        i = len(self._detected_videos) - 1

        # Create frame for this video
        video_frame = ctk.CTkFrame(self.results_scroll, fg_color="gray20")
        video_frame.grid(row=i, column=0, sticky="ew", pady=(0, 8))
        video_frame.grid_columnconfigure(1, weight=1)

        # Checkbox
        var = ctk.BooleanVar(value=True)
        checkbox = ctk.CTkCheckBox(
            video_frame,
            text="",
            variable=var,
            width=24,
        )
        checkbox.grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=8)
        self._checkboxes.append((checkbox, var, result))

        # Source badge
        source_colors = {
            "cloudflare": "#f6821f",
            "vimeo": "#1ab7ea",
            "youtube": "#ff0000",
            "kinescope": "#6b5b95",
            "getcourse": "#ff6600",
            "generic": "#333333",
        }
        badge_color = source_colors.get(video.source, "gray40")
        source_label = ctk.CTkLabel(
            video_frame,
            text=video.source.upper()[:6],
            width=50,
            height=20,
            corner_radius=4,
            fg_color=badge_color,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        source_label.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=(8, 2))

        # Title/URL
        display_text = video.title or (video.url[:60] + "..." if len(video.url) > 60 else video.url)
        title_label = ctk.CTkLabel(
            video_frame,
            text=display_text,
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        title_label.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))

    def _finish_detection(self, error: Optional[str]) -> None:
        """Handle detection completion."""
        self.detect_button.configure(state="normal", text="Detect")

        if error:
            self.log.error(f"[Detect] Detection failed: {error}")
            if "close" in error.lower() and "browser" in error.lower():
                self._set_status(error, error=True)
            else:
                self._set_status(f"Error: {error[:100]}", error=True)
            if not self._detected_videos:
                self.placeholder_label.configure(text="Detection failed. Try again.")
            return

        count = len(self._detected_videos)
        self.log.info(f"[Detect] Detection complete, found {count} video(s)")

        if count == 0:
            self._set_status("No videos found on this page.", error=True)
        else:
            self._set_status(f"Found {count} video{'s' if count != 1 else ''}. Select videos to add to queue.")

    def _clear_results(self) -> None:
        """Clear previous results."""
        for widget in self.results_scroll.winfo_children():
            widget.destroy()

        self._detected_videos = []
        self._checkboxes = []

        # Show placeholder again
        self.placeholder_label = ctk.CTkLabel(
            self.results_scroll,
            text="Scanning for videos...",
            font=ctk.CTkFont(size=12),
            text_color="gray50",
        )
        self.placeholder_label.grid(row=0, column=0, pady=40)

        self.select_all_button.configure(state="disabled")
        self.add_button.configure(state="disabled")

        # Force UI update
        self.update_idletasks()

    def _set_status(self, message: str, error: bool = False) -> None:
        """Update status label."""
        color = "#ff6666" if error else "gray60"
        self.status_label.configure(text=message, text_color=color)

    def _update_placeholder(self) -> None:
        """Update placeholder based on profile setup status."""
        from core.browser_detect import is_detection_profile_setup

        if is_detection_profile_setup():
            text = (
                "Ready to detect videos.\n\n"
                "Enter a URL and click Detect."
            )
        else:
            text = (
                "Login profile not set up.\n\n"
                "Go to Settings and click 'Setup Profile'\n"
                "to log in to your video sites first."
            )

        self.placeholder_label = ctk.CTkLabel(
            self.results_scroll,
            text=text,
            font=ctk.CTkFont(size=12),
            text_color="gray50",
        )
        self.placeholder_label.grid(row=0, column=0, pady=30)

        if success:
            self.log.info(f"[Detect] Profile setup complete")
            self._set_status(message)
            self.setup_button.configure(text="Re-setup Profile", fg_color="gray40", hover_color="gray50")
            # Update placeholder
            self._clear_results()
            self._update_placeholder()
        else:
            self.log.error(f"[Detect] Profile setup failed: {message}")
            self._set_status(message, error=True)
            self.setup_button.configure(text="Setup Profile")

    def _on_select_all(self) -> None:
        """Toggle all checkboxes."""
        # Check if all are selected
        all_selected = all(var.get() for _, var, _ in self._checkboxes)

        # Toggle all
        new_value = not all_selected
        for _, var, result in self._checkboxes:
            var.set(new_value)
            result.selected = new_value

        # Update button text
        self.select_all_button.configure(text="Deselect All" if new_value else "Select All")

    def _on_add_to_queue(self) -> None:
        """Add selected videos to the download queue."""
        selected_urls = []
        for _, var, result in self._checkboxes:
            if var.get():
                selected_urls.append(result.url)

        if not selected_urls:
            self._set_status("No videos selected", error=True)
            return

        self.log.info(f"[Detect] Adding {len(selected_urls)} video(s) to queue")

        # Call the callback with selected URLs
        try:
            self.on_add_videos(selected_urls)
            # Close dialog on success
            self.destroy()
        except Exception as e:
            self.log.error(f"[Detect] Error adding videos: {e}")
            self._set_status(f"Error: {e}", error=True)
            import traceback
            traceback.print_exc()
