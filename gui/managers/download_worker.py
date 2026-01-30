"""
Threaded download worker for GUI.
"""

import subprocess
import sys
import threading
from typing import Optional

from core.downloader import ProgressParser, VimeoDownloader
from core.detector import VideoSource
from ..models.queue_item import QueueItem, QueueStatus
from ..models.settings import AppSettings
from .event_processor import EventProcessor, EventType


class DownloadWorker:
    """
    Executes downloads in a separate thread with progress reporting.
    """

    def __init__(
        self,
        item: QueueItem,
        settings: AppSettings,
        event_processor: EventProcessor,
    ):
        self.item = item
        self.settings = settings
        self.events = event_processor

        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        """Start the download in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        """Request cancellation of the download."""
        self._cancel_event.set()
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def is_running(self) -> bool:
        """Check if the worker is currently running."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """Main worker thread function."""
        try:
            # Phase 1: Analysis
            self.events.push(EventType.STATUS_CHANGE, self.item.id, QueueStatus.ANALYZING)

            if self._cancel_event.is_set():
                self._handle_cancelled()
                return

            # Create downloader and analyze
            downloader = VimeoDownloader(
                url=self.item.url,
                password=None,
                browser=self.settings.browser,
                profile=self.settings.browser_profile,
                skip_cookies=self.settings.no_cookies,
            )

            if not downloader.analyze():
                self._handle_error("Failed to analyze video URL")
                return

            if self._cancel_event.is_set():
                self._handle_cancelled()
                return

            # Extract info from analyzer
            detector = downloader.detector
            if detector:
                self.item.platform = detector.source.value
                self.item.is_video_only = detector.is_video_only_stream()

                # Try to get title (for Vimeo/YouTube)
                if detector.video_id and detector.source in (VideoSource.VIMEO, VideoSource.YOUTUBE):
                    self.item.title = f"Video {detector.video_id}"

            self.events.push(EventType.ANALYSIS_COMPLETE, self.item.id, {
                "platform": self.item.platform,
                "is_video_only": self.item.is_video_only,
                "title": self.item.title,
            })

            if self._cancel_event.is_set():
                self._handle_cancelled()
                return

            # Phase 2: Download
            self.events.push(EventType.STATUS_CHANGE, self.item.id, QueueStatus.DOWNLOADING)

            success = self._execute_download(downloader)

            if self._cancel_event.is_set():
                self._handle_cancelled()
                return

            if success:
                self.events.push(EventType.DOWNLOAD_COMPLETE, self.item.id)
            else:
                self._handle_error("Download failed")

        except Exception as e:
            self._handle_error(str(e))

    def _execute_download(self, downloader: VimeoDownloader) -> bool:
        """Execute the actual download with progress tracking."""
        if not downloader.command_builder:
            return False

        # Build command with custom format string if quality cap is enabled
        cmd = downloader.command_builder.build_ytdlp_command(
            output_path=self.settings.output_folder,
            use_aria2=self.settings.use_aria2,
            fast=self.settings.fast_mode,
            filename=None,
        )

        # If quality cap is enabled, modify the format string in the command
        if self.settings.quality_cap_1080p:
            cmd = self._apply_quality_cap(cmd)

        # Create progress callback
        def progress_callback(percent: float, speed: str, eta: str, status: str) -> None:
            if not self._cancel_event.is_set():
                self.events.push(EventType.PROGRESS_UPDATE, self.item.id, {
                    "percent": percent,
                    "speed": speed,
                    "eta": eta,
                    "status": status,
                })

        parser = ProgressParser(progress_callback=progress_callback)

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
            )

            for line in self._process.stdout:
                if self._cancel_event.is_set():
                    self._process.terminate()
                    return False
                parser.parse_line(line)

            self._process.wait()
            return self._process.returncode == 0

        except Exception as e:
            self._handle_error(f"Process error: {e}")
            return False
        finally:
            self._process = None

    def _apply_quality_cap(self, cmd: list) -> list:
        """Apply 1080p quality cap to the command."""
        result = []
        i = 0
        while i < len(cmd):
            if cmd[i] == "-f" and i + 1 < len(cmd):
                result.append(cmd[i])
                # Replace the format string with capped version
                result.append(self.settings.get_format_string())
                i += 2
            else:
                result.append(cmd[i])
                i += 1
        return result

    def _handle_error(self, message: str) -> None:
        """Handle download error."""
        self.item.error_message = message
        self.events.push(EventType.DOWNLOAD_ERROR, self.item.id, message)

    def _handle_cancelled(self) -> None:
        """Handle cancellation."""
        self.events.push(EventType.STATUS_CHANGE, self.item.id, QueueStatus.CANCELLED)
