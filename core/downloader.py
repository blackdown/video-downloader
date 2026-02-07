"""
Download orchestration and execution.
"""

import subprocess
import re
from typing import Optional
from urllib.parse import urlparse
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, DownloadColumn, TransferSpeedColumn, TaskProgressColumn
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from .detector import VimeoDetector, VimeoType, VideoSource, WebpageScraper
from .auth import CookieManager
from .commands import CommandBuilder
from .runtime import ytdlp_cmd, ffmpeg_env


console = Console()


class ProgressParser:
    """Parse yt-dlp progress output and update rich progress bar."""

    # Pattern for yt-dlp progress lines like:
    # [download]  45.2% of 100.00MiB at 5.00MiB/s ETA 00:10
    PROGRESS_PATTERN = re.compile(
        r'\[download\]\s+(\d+\.?\d*)%\s+of\s+~?([\d.]+)(\w+)\s+at\s+([\d.]+)(\w+)/s\s+ETA\s+(\d+:\d+)'
    )
    # Simpler pattern that just captures percentage (fallback for varied formats)
    SIMPLE_PROGRESS_PATTERN = re.compile(
        r'\[download\]\s+(\d+\.?\d*)%'
    )
    # Pattern for fragment progress like:
    # [download] Downloading fragment 5 of 100
    FRAGMENT_PATTERN = re.compile(
        r'\[download\]\s+Downloading\s+(?:item|video|fragment)\s+(\d+)\s+of\s+(\d+)'
    )
    # Pattern for completed download
    COMPLETE_PATTERN = re.compile(
        r'\[download\]\s+100%\s+of'
    )
    # Pattern for destination file
    DESTINATION_PATTERN = re.compile(
        r'\[download\]\s+Destination:\s+(.+)'
    )
    # Pattern for merging
    MERGE_PATTERN = re.compile(
        r'\[Merger\]|Merging formats'
    )

    def __init__(self, progress_callback=None):
        """
        Initialize the progress parser.

        Args:
            progress_callback: Optional callable(percent, speed, eta, status) for GUI updates
        """
        self.total_size = 0
        self.downloaded = 0
        self.speed = ""
        self.eta = ""
        self.percent = 0.0
        self.destination = ""
        self.status = "Starting..."
        self.is_complete = False
        self._progress_callback = progress_callback

    def parse_line(self, line: str) -> bool:
        """Parse a line of yt-dlp output. Returns True if progress was updated."""
        line = line.strip()
        if not line:
            return False

        updated = False

        # Check for destination
        dest_match = self.DESTINATION_PATTERN.search(line)
        if dest_match:
            self.destination = dest_match.group(1)
            self.status = f"Downloading: {self.destination.split('/')[-1]}"
            updated = True

        # Check for standard progress (full format with size/speed/eta)
        if not updated:
            match = self.PROGRESS_PATTERN.search(line)
            if match:
                self.percent = float(match.group(1))
                size_val = float(match.group(2))
                size_unit = match.group(3)
                speed_val = float(match.group(4))
                speed_unit = match.group(5)
                self.eta = match.group(6)

                # Convert to bytes for display
                self.total_size = self._to_bytes(size_val, size_unit)
                self.downloaded = int(self.total_size * self.percent / 100)
                self.speed = f"{speed_val:.1f} {speed_unit}/s"
                self.status = "Downloading"
                updated = True

        # Check for fragment progress (common with YouTube DASH)
        if not updated:
            frag_match = self.FRAGMENT_PATTERN.search(line)
            if frag_match:
                current = int(frag_match.group(1))
                total = int(frag_match.group(2))
                self.percent = (current / total) * 100
                self.status = f"Fragment {current}/{total}"
                updated = True

        # Fallback: simple percentage pattern
        if not updated:
            simple_match = self.SIMPLE_PROGRESS_PATTERN.search(line)
            if simple_match:
                self.percent = float(simple_match.group(1))
                self.status = "Downloading"
                updated = True

        # Check for completion
        if not updated and self.COMPLETE_PATTERN.search(line):
            self.percent = 100.0
            self.is_complete = True
            self.status = "Download complete"
            updated = True

        # Check for merging
        if not updated and self.MERGE_PATTERN.search(line):
            self.status = "Merging audio and video..."
            updated = True

        # Invoke callback if we have one and something changed
        if updated and self._progress_callback:
            try:
                self._progress_callback(self.percent, self.speed, self.eta, self.status)
            except Exception:
                pass  # Don't let callback errors break parsing

        return updated

    def _to_bytes(self, value: float, unit: str) -> int:
        """Convert size value to bytes."""
        unit = unit.upper()
        multipliers = {
            'B': 1,
            'KIB': 1024, 'KB': 1000,
            'MIB': 1024**2, 'MB': 1000**2,
            'GIB': 1024**3, 'GB': 1000**3,
        }
        return int(value * multipliers.get(unit, 1))


class VimeoDownloader:
    """Main downloader class that orchestrates the download process."""
    
    def __init__(self, url: str, password: Optional[str] = None,
                 browser: str = "chrome", profile: Optional[str] = None,
                 skip_cookies: bool = False):
        self.url = url
        self.password = password
        self.browser = browser
        self.profile = profile
        self.skip_cookies = skip_cookies

        self.detector = None
        self.cookie_manager = None
        self.command_builder = None
        
    def analyze(self) -> bool:
        """Analyse the video and prepare for download."""

        console.print(f"[cyan]Analysing video:[/cyan] {self.url}")

        # Extract cookies (unless skipped)
        self.cookie_manager = CookieManager(self.browser, self.profile)
        if self.skip_cookies:
            cookies = {}
            console.print("[dim]Skipping cookie extraction[/dim]")
        else:
            cookies = self.cookie_manager.extract_cookies()

        # Detect video type
        self.detector = VimeoDetector(self.url, cookies)
        video_id, video_hash = self.detector.parse_url()

        # If URL doesn't match known patterns, try scraping the webpage
        if not video_id:
            console.print("[dim]URL not recognized, scanning webpage for embedded videos...[/dim]")

            # Extract cookies for the target domain (not just vimeo.com)
            if not self.skip_cookies:
                domain = urlparse(self.url).netloc
                console.print(f"[dim]Extracting cookies for {domain}...[/dim]")
                cookies = self.cookie_manager.extract_cookies(domain) or {}

            scraper = WebpageScraper(self.url, cookies, browser=self.browser)
            found_urls = scraper.fetch_and_scan()

            if found_urls:
                best_url, source = found_urls[0]
                console.print(f"[green]✓ Found embedded video:[/green] {source.value}")
                console.print(f"[dim]  {best_url[:80]}{'...' if len(best_url) > 80 else ''}[/dim]")

                # Show other found URLs if any
                if len(found_urls) > 1:
                    console.print(f"[dim]  (and {len(found_urls) - 1} more video URL(s) found)[/dim]")

                # Re-detect with the found URL
                self.url = best_url
                self.detector = VimeoDetector(best_url, cookies)
                video_id, video_hash = self.detector.parse_url()

        if not video_id:
            console.print("[red]✗ Could not find video URL - not a recognized video platform or webpage with embedded video[/red]")
            return False

        source = self.detector.source

        # Display detection results based on source
        if source == VideoSource.YOUTUBE:
            console.print(f"[green]✓ YouTube video detected[/green] (ID: {video_id})")
        elif source == VideoSource.GETCOURSE:
            console.print(f"[green]✓ GetCourse stream detected[/green] (ID: {video_id}...)")
        elif source == VideoSource.KINESCOPE:
            console.print(f"[green]✓ Kinescope stream detected[/green] (ID: {video_id[:8]}...)")
            # Check if this is a video-only stream
            if self.detector.is_video_only_stream():
                console.print("[bold yellow]⚠ WARNING: This is a video-only stream URL (type=video)![/bold yellow]")
                console.print("[yellow]  Audio will be missing. You need the master playlist URL instead.[/yellow]")
                console.print("[yellow]  Look for a URL without 'type=video' or with 'type=audio' for the audio track.[/yellow]")
                console.print("")
        elif source == VideoSource.DIRECT_STREAM:
            console.print("[green]✓ Direct m3u8 stream URL detected[/green]")
            # Check if this is a video-only stream
            if self.detector.is_video_only_stream():
                console.print("[bold yellow]⚠ WARNING: This appears to be a video-only stream URL![/bold yellow]")
                console.print("[yellow]  Audio may be missing. Use the Master playlist URL instead.[/yellow]")
                console.print("[yellow]  Master URLs typically contain '/primary/' and end with 'playlist.m3u8'[/yellow]")
                console.print("")
        else:
            console.print(f"[green]✓ Video ID:[/green] {video_id}")
            if video_hash:
                console.print(f"[green]✓ Video hash:[/green] {video_hash}")

        # Detect type (skip for YouTube/Kinescope/GetCourse/direct streams - yt-dlp handles them)
        if source in (VideoSource.YOUTUBE, VideoSource.KINESCOPE, VideoSource.GETCOURSE, VideoSource.DIRECT_STREAM):
            video_type = VimeoType.PUBLIC
        else:
            video_type = self.detector.detect_type()
            console.print(f"[green]✓ Video type:[/green] {video_type.value}")
        
        # Build command
        cookie_string = None if self.skip_cookies else self.cookie_manager.get_cookie_string_for_ytdlp()
        self.command_builder = CommandBuilder(
            video_id, video_hash, video_type,
            self.password, cookie_string, original_url=self.url,
            source=source
        )
        
        # Show warnings
        if video_type == VimeoType.PASSWORD_PROTECTED and not self.password:
            console.print("[yellow]⚠ Video is password-protected. Use --password flag.[/yellow]")
            return False
        
        if video_type == VimeoType.LOGIN_REQUIRED:
            console.print("[yellow]⚠ Video requires login. Using browser cookies.[/yellow]")
        
        if video_type == VimeoType.EMBED_ONLY:
            console.print("[yellow]⚠ Video is embed-only. You may need the embedding page URL.[/yellow]")
        
        return True
    
    def download(self, output_path: str = ".", use_aria2: bool = False,
                 dry_run: bool = False, fast: bool = False, filename: str = None,
                 show_progress: bool = True) -> bool:
        """Execute the download."""

        if not self.command_builder:
            console.print("[red]Run analyze() first[/red]")
            return False

        # Build command
        cmd = self.command_builder.build_ytdlp_command(output_path, use_aria2, fast, filename)

        if dry_run:
            console.print("\n[cyan]Command that would be executed:[/cyan]")
            console.print(self.command_builder.get_command_string(False, output_path, use_aria2, fast, filename))
            return True

        console.print("\n[cyan]Starting download...[/cyan]\n")

        if show_progress:
            return self._download_with_progress(cmd)
        else:
            return self._download_simple(cmd)

    def _download_simple(self, cmd: list) -> bool:
        """Execute download without rich progress (fallback)."""
        try:
            result = subprocess.run(cmd, check=True, env=ffmpeg_env())
            console.print("\n[green]✓ Download completed successfully![/green]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"\n[red]✗ Download failed with error code {e.returncode}[/red]")
            return False
        except FileNotFoundError:
            console.print("[red]✗ yt-dlp module not found. Please install it: pip install yt-dlp[/red]")
            return False

    def _download_with_progress(self, cmd: list) -> bool:
        """Execute download with rich progress bar."""
        parser = ProgressParser()

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=ffmpeg_env(),
            )

            with Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                TaskProgressColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
                transient=False,
            ) as progress:
                task = progress.add_task("Downloading...", total=100)

                for line in process.stdout:
                    if parser.parse_line(line):
                        progress.update(
                            task,
                            completed=parser.percent,
                            description=parser.status[:30] + "..." if len(parser.status) > 30 else parser.status
                        )

                    # Also show non-progress lines that might be important
                    if not parser.PROGRESS_PATTERN.search(line):
                        stripped = line.strip()
                        if stripped and not stripped.startswith('[download]'):
                            # Show important messages outside progress bar
                            if any(x in stripped.lower() for x in ['error', 'warning', 'merger', 'extracting']):
                                console.print(f"[dim]{stripped}[/dim]")

                process.wait()

            if process.returncode == 0:
                console.print("\n[green]✓ Download completed successfully![/green]")
                if parser.destination:
                    console.print(f"[dim]Saved to: {parser.destination}[/dim]")
                return True
            else:
                console.print(f"\n[red]✗ Download failed with error code {process.returncode}[/red]")
                return False

        except FileNotFoundError:
            console.print("[red]✗ yt-dlp module not found. Please install it: pip install yt-dlp[/red]")
            return False
        except Exception as e:
            console.print(f"[red]✗ Download error: {e}[/red]")
            return False

    def list_formats(self) -> bool:
        """List available formats for the video."""

        if not self.command_builder:
            console.print("[red]Run analyze() first[/red]")
            return False

        url = self.command_builder.get_url()
        cmd = [*ytdlp_cmd(), "-F", "--no-cookies-from-browser", url]

        console.print("\n[cyan]Available formats:[/cyan]\n")

        try:
            subprocess.run(cmd, check=True, env=ffmpeg_env())
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"\n[red]✗ Failed to list formats[/red]")
            return False
