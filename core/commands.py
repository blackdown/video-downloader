"""
Command construction for different download methods.
"""

import sys
from typing import List, Optional
from .detector import VimeoType


class CommandBuilder:
    """Build appropriate download commands based on video type."""

    def __init__(self, video_id: str, video_hash: Optional[str],
                 video_type: VimeoType, password: Optional[str] = None,
                 cookie_string: Optional[str] = None, original_url: Optional[str] = None):
        self.video_id = video_id
        self.video_hash = video_hash
        self.video_type = video_type
        self.password = password
        self.cookie_string = cookie_string
        self.original_url = original_url

    def get_url(self) -> str:
        """Get the appropriate URL for download."""
        # For direct m3u8 URLs, use the original URL
        if self.video_id == "direct_m3u8" and self.original_url:
            return self.original_url
        if self.video_hash:
            return f"https://vimeo.com/{self.video_id}/{self.video_hash}"
        return f"https://vimeo.com/{self.video_id}"
    
    def build_ytdlp_command(self, output_path: str = ".", use_aria2: bool = False, fast: bool = False, filename: str = None) -> List[str]:
        """Build yt-dlp command with appropriate flags."""

        url = self.get_url()
        referer = url

        # Use more concurrent fragments in fast mode
        concurrent = "32" if fast else "16"

        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-N", concurrent,  # Parallel fragments
            "--no-warnings",   # Hide warnings
            "--progress",      # Ensure progress bar shows
            "--newline",       # Output progress on new lines (cleaner)
        ]
        
        # Add cookies if available, otherwise explicitly disable
        if self.cookie_string:
            cmd.extend(["--cookies-from-browser", self.cookie_string])
        else:
            cmd.append("--no-cookies-from-browser")

        # Add password if needed
        if self.password and self.video_type == VimeoType.PASSWORD_PROTECTED:
            cmd.extend(["--video-password", self.password])

        # Add referer (skip for direct m3u8 URLs)
        if self.video_id != "direct_m3u8":
            cmd.extend(["--referer", referer])
        
        # Quality and format selection
        if self.video_id == "direct_m3u8":
            # For direct m3u8, let yt-dlp figure it out or use ffmpeg
            cmd.extend([
                "--merge-output-format", "mp4",
            ])
        else:
            # For normal Vimeo URLs, select best video+audio
            cmd.extend([
                "-f", "bv*+ba/b",
                "-S", "codec:avc,res,ext",
                "--merge-output-format", "mp4",
                "--postprocessor-args", "ffmpeg:-movflags +faststart"
            ])
        
        # Downloader selection
        if use_aria2:
            cmd.extend([
                "--downloader", "aria2c",
                "--downloader-args", "aria2c:-x 16 -s 16 -k 1M"
            ])
        elif self.video_id == "direct_m3u8":
            # Use ffmpeg for m3u8 streams - better audio handling
            # -loglevel warning suppresses the verbose HTTP request output
            cmd.extend([
                "--downloader", "ffmpeg",
                "--downloader-args", "ffmpeg:-loglevel warning"
            ])
        else:
            cmd.extend(["--downloader", "native"])
        
        # Output path and filename
        if filename:
            # User specified filename
            cmd.extend(["-o", f"{output_path}/{filename}.%(ext)s"])
        elif self.video_id == "direct_m3u8":
            # Direct m3u8 - use timestamp-based name
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cmd.extend(["-o", f"{output_path}/vimeo_{timestamp}.%(ext)s"])
        else:
            # Normal Vimeo URL - use title or video ID
            cmd.extend(["-o", f"{output_path}/%(title)s [%(id)s].%(ext)s"])

        # Add URL
        cmd.append(url)
        
        return cmd
    
    def build_streamlink_command(self, output_path: str = ".") -> tuple:
        """Build streamlink command (alternative method)."""
        
        player_url = f"https://player.vimeo.com/video/{self.video_id}"
        output_file = f"{output_path}/vimeo_{self.video_id}.mp4"
        
        cmd = [
            "streamlink",
            "-O", player_url,
            "best",
            "--stream-segment-threads", "5"
        ]
        
        return cmd, output_file
    
    def get_command_string(self, use_streamlink: bool = False,
                          output_path: str = ".", use_aria2: bool = False, fast: bool = False, filename: str = None) -> str:
        """Get the full command as a string (for display/debugging)."""

        if use_streamlink:
            cmd, output = self.build_streamlink_command(output_path)
            ffmpeg_part = f"ffmpeg -i pipe:0 -c copy -movflags +faststart {output}"
            return " | ".join([" ".join(cmd), ffmpeg_part])
        else:
            cmd = self.build_ytdlp_command(output_path, use_aria2, fast, filename)
            return " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd)
