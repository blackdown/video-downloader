"""
Threaded download worker for GUI.
"""

import subprocess
import sys
import threading
import traceback
from typing import Optional

from core.downloader import ProgressParser, VimeoDownloader
from core.detector import VideoSource
from core.runtime import ffmpeg_env
from ..models.queue_item import QueueItem, QueueStatus
from ..models.settings import AppSettings
from .event_processor import EventProcessor, EventType
from .logger import get_logger


class DownloadWorker:
    """
    Executes downloads in a separate thread with progress reporting.
    """

    def __init__(
        self,
        item: QueueItem,
        settings: AppSettings,
        event_processor: EventProcessor,
        analyze_only: bool = False,
    ):
        self.item = item
        self.settings = settings
        self.events = event_processor
        self.analyze_only = analyze_only
        self.log = get_logger()

        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._process: Optional[subprocess.Popen] = None
        self._downloader: Optional[VimeoDownloader] = None  # Store for later download

    def start(self) -> None:
        """Start the download in a background thread."""
        if self._thread and self._thread.is_alive():
            self.log.warning(f"[{self.item.id}] Worker already running, ignoring start request")
            return

        mode = "analyze" if self.analyze_only else "download"
        self.log.info(f"[{self.item.id}] Starting {mode} worker for: {self.item.url[:80]}")
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        """Request cancellation of the download."""
        self.log.info(f"[{self.item.id}] Cancel requested")
        self._cancel_event.set()
        if self._process:
            try:
                self._process.terminate()
                self.log.info(f"[{self.item.id}] Process terminated")
            except Exception as e:
                self.log.error(f"[{self.item.id}] Error terminating process: {e}")

    def is_running(self) -> bool:
        """Check if the worker is currently running."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """Main worker thread function."""
        try:
            # Phase 1: Analysis
            self.log.info(f"[{self.item.id}] Phase 1: Analyzing URL")
            self.events.push(EventType.STATUS_CHANGE, self.item.id, QueueStatus.ANALYZING)

            if self._cancel_event.is_set():
                self._handle_cancelled()
                return

            # Create downloader and analyze
            # Use cookies based on settings - needed for webpage scraping of members-only sites
            skip_cookies = self.settings.no_cookies
            self.log.debug(f"[{self.item.id}] Creating VimeoDownloader (skip_cookies={skip_cookies})")
            self._downloader = VimeoDownloader(
                url=self.item.url,
                password=None,
                browser=self.settings.browser,
                profile=self.settings.browser_profile,
                skip_cookies=skip_cookies,
            )

            self.log.debug(f"[{self.item.id}] Calling downloader.analyze()")
            if not self._downloader.analyze():
                self._handle_error("Failed to analyze video URL")
                return

            if self._cancel_event.is_set():
                self._handle_cancelled()
                return

            # Extract info from analyzer
            detector = self._downloader.detector
            if detector:
                self.item.platform = detector.source.value
                self.item.is_video_only = detector.is_video_only_stream()
                self.log.info(f"[{self.item.id}] Detected platform: {self.item.platform}, video_only: {self.item.is_video_only}")

                # Try to get title (for Vimeo/YouTube)
                if detector.video_id and detector.source in (VideoSource.VIMEO, VideoSource.YOUTUBE):
                    self.item.title = f"Video {detector.video_id}"

            self.events.push(EventType.ANALYSIS_COMPLETE, self.item.id, {
                "platform": self.item.platform,
                "is_video_only": self.item.is_video_only,
                "title": self.item.title,
            })

            # If analyze_only, stop here and set status to READY
            if self.analyze_only:
                self.log.info(f"[{self.item.id}] Analysis complete (analyze_only mode)")
                self.events.push(EventType.STATUS_CHANGE, self.item.id, QueueStatus.READY)
                return

            if self._cancel_event.is_set():
                self._handle_cancelled()
                return

            # Phase 2: Download
            self._run_download()

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.log.error(f"[{self.item.id}] Exception in worker: {error_msg}")
            self.log.debug(f"[{self.item.id}] Traceback:\n{traceback.format_exc()}")
            self._handle_error(error_msg)

    def _run_download(self) -> None:
        """Run the download phase (can be called separately for READY items)."""
        self.log.info(f"[{self.item.id}] Phase 2: Starting download")
        self.events.push(EventType.STATUS_CHANGE, self.item.id, QueueStatus.DOWNLOADING)

        success = self._execute_download(self._downloader)

        if self._cancel_event.is_set():
            self._handle_cancelled()
            return

        if success:
            self.log.info(f"[{self.item.id}] Download completed successfully")
            self.events.push(EventType.DOWNLOAD_COMPLETE, self.item.id)
        else:
            self._handle_error("Download failed (yt-dlp returned non-zero exit code)")

    def start_download(self) -> None:
        """Start just the download phase for an already-analyzed item."""
        if self._thread and self._thread.is_alive():
            self.log.warning(f"[{self.item.id}] Worker already running")
            return

        if not self._downloader:
            self.log.error(f"[{self.item.id}] Cannot start download - not analyzed yet")
            return

        self.log.info(f"[{self.item.id}] Starting download for analyzed item")
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run_download, daemon=True)
        self._thread.start()

    def _execute_download(self, downloader: VimeoDownloader) -> bool:
        """Execute the actual download with progress tracking."""
        if not downloader.command_builder:
            self.log.error(f"[{self.item.id}] No command builder available")
            return False

        # Build command with custom format string if quality cap is enabled
        cmd = downloader.command_builder.build_ytdlp_command(
            output_path=self.settings.output_folder,
            use_aria2=self.settings.use_aria2,
            fast=self.settings.fast_mode,
            filename=self.item.custom_filename,
        )

        # If quality cap is enabled, modify the format string in the command
        if self.settings.quality_cap_1080p:
            cmd = self._apply_quality_cap(cmd)

        # Log the command
        cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd)
        self.log.info(f"[{self.item.id}] Executing command: {cmd_str[:200]}...")
        self.log.debug(f"[{self.item.id}] Full command: {cmd_str}")

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
                env=ffmpeg_env(),
            )
            self.log.debug(f"[{self.item.id}] Process started with PID: {self._process.pid}")

            output_lines = []
            for line in self._process.stdout:
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    # Log errors and warnings from yt-dlp
                    if "error" in line.lower() or "ERROR" in line:
                        self.log.error(f"[{self.item.id}] yt-dlp: {line}")
                    elif "warning" in line.lower() or "WARNING" in line:
                        self.log.warning(f"[{self.item.id}] yt-dlp: {line}")

                if self._cancel_event.is_set():
                    self._process.terminate()
                    self.log.info(f"[{self.item.id}] Download cancelled by user")
                    return False
                parser.parse_line(line)

            self._process.wait()
            exit_code = self._process.returncode
            self.log.info(f"[{self.item.id}] Process exited with code: {exit_code}")

            if exit_code != 0:
                # Log last few lines of output for debugging
                self.log.error(f"[{self.item.id}] Download failed. Last 10 lines of output:")
                for line in output_lines[-10:]:
                    self.log.error(f"[{self.item.id}]   {line}")

            return exit_code == 0

        except FileNotFoundError as e:
            self.log.error(f"[{self.item.id}] Command not found: {e}")
            self._handle_error(f"Command not found: {e}")
            return False
        except Exception as e:
            self.log.error(f"[{self.item.id}] Process error: {type(e).__name__}: {e}")
            self.log.debug(f"[{self.item.id}] Traceback:\n{traceback.format_exc()}")
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
        self.log.error(f"[{self.item.id}] Error: {message}")
        self.item.error_message = message
        self.events.push(EventType.DOWNLOAD_ERROR, self.item.id, message)

    def _handle_cancelled(self) -> None:
        """Handle cancellation."""
        self.log.info(f"[{self.item.id}] Download cancelled")
        self.events.push(EventType.STATUS_CHANGE, self.item.id, QueueStatus.CANCELLED)
