"""
Stream detection warning indicator widget.
"""

import customtkinter as ctk


class StreamWarning(ctk.CTkFrame):
    """
    Visual indicator for video/audio stream detection.

    Shows green "VIDEO + AUDIO" for complete streams,
    yellow "VIDEO ONLY" warning for video-only streams.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._setup_ui()
        self.set_unknown()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.label = ctk.CTkLabel(
            self,
            text="Stream Detection",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.label.pack(anchor="w", pady=(0, 4))

        self.indicator_frame = ctk.CTkFrame(
            self,
            height=30,
            corner_radius=6,
        )
        self.indicator_frame.pack(fill="x")
        self.indicator_frame.pack_propagate(False)

        self.indicator_label = ctk.CTkLabel(
            self.indicator_frame,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.indicator_label.pack(expand=True)

    def set_video_and_audio(self) -> None:
        """Set indicator to show full stream (video + audio)."""
        self.indicator_frame.configure(fg_color="#2d5a27")  # Green
        self.indicator_label.configure(
            text="VIDEO + AUDIO",
            text_color="white",
        )

    def set_video_only(self) -> None:
        """Set indicator to show video-only warning."""
        self.indicator_frame.configure(fg_color="#8a7a00")  # Yellow/amber
        self.indicator_label.configure(
            text="VIDEO ONLY - No audio!",
            text_color="white",
        )

    def set_unknown(self) -> None:
        """Set indicator to unknown state."""
        self.indicator_frame.configure(fg_color="gray40")
        self.indicator_label.configure(
            text="Not analyzed",
            text_color="gray70",
        )

    def update_from_item(self, is_video_only: bool, is_analyzed: bool) -> None:
        """Update indicator based on queue item state."""
        if not is_analyzed:
            self.set_unknown()
        elif is_video_only:
            self.set_video_only()
        else:
            self.set_video_and_audio()
