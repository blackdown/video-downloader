"""
Download orchestration and execution.
"""

import subprocess
import sys
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from .detector import VimeoDetector, VimeoType
from .auth import CookieManager
from .commands import CommandBuilder


console = Console()


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
        
        if not video_id:
            console.print("[red]✗ Invalid Vimeo URL[/red]")
            return False

        if video_id == "direct_m3u8":
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
        
        # Detect type (skip for direct m3u8 URLs)
        if video_id == "direct_m3u8":
            video_type = VimeoType.PUBLIC
        else:
            video_type = self.detector.detect_type()
            console.print(f"[green]✓ Video type:[/green] {video_type.value}")
        
        # Build command
        cookie_string = None if self.skip_cookies else self.cookie_manager.get_cookie_string_for_ytdlp()
        self.command_builder = CommandBuilder(
            video_id, video_hash, video_type,
            self.password, cookie_string, original_url=self.url
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
                 dry_run: bool = False, fast: bool = False, filename: str = None) -> bool:
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
        
        # Execute
        console.print("\n[cyan]Starting download...[/cyan]\n")
        
        try:
            result = subprocess.run(cmd, check=True)
            console.print("\n[green]✓ Download completed successfully![/green]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"\n[red]✗ Download failed with error code {e.returncode}[/red]")
            return False
        except FileNotFoundError:
            console.print("[red]✗ yt-dlp module not found. Please install it: pip install yt-dlp[/red]")
            return False

    def list_formats(self) -> bool:
        """List available formats for the video."""

        if not self.command_builder:
            console.print("[red]Run analyze() first[/red]")
            return False

        url = self.command_builder.get_url()
        cmd = [sys.executable, "-m", "yt_dlp", "-F", "--no-cookies-from-browser", url]

        console.print("\n[cyan]Available formats:[/cyan]\n")

        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"\n[red]✗ Failed to list formats[/red]")
            return False
