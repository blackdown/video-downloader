"""
Command construction for different download methods.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional
from .detector import VimeoType, VideoSource


def get_bundled_path(tool_name: str) -> Optional[str]:
    """
    Find bundled executable path for a tool.
    Checks for bundled versions when running as a PyInstaller exe.
    """
    # When running as bundled exe, check relative paths
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent

        # Check for bundled tools
        if tool_name == "yt-dlp":
            for check_path in [
                base_path / "yt-dlp" / "yt-dlp.exe",
                base_path / "yt-dlp.exe",
            ]:
                if check_path.exists():
                    return str(check_path)
        elif tool_name == "ffmpeg":
            for check_path in [
                base_path / "ffmpeg" / "ffmpeg.exe",
                base_path / "ffmpeg.exe",
            ]:
                if check_path.exists():
                    return str(check_path)

    return None


def get_ytdlp_command() -> List[str]:
    """Get the command to run yt-dlp (bundled or module)."""
    bundled = get_bundled_path("yt-dlp")
    if bundled:
        return [bundled]
    else:
        return [sys.executable, "-m", "yt_dlp"]


def get_ffmpeg_path() -> Optional[str]:
    """Get path to ffmpeg (bundled or system)."""
    bundled = get_bundled_path("ffmpeg")
    if bundled:
        return bundled
    # Fall back to system ffmpeg
    return None


class CommandBuilder:
    """Build appropriate download commands based on video type."""

    def __init__(self, video_id: str, video_hash: Optional[str],
                 video_type: VimeoType, password: Optional[str] = None,
                 cookie_string: Optional[str] = None, original_url: Optional[str] = None,
                 source: VideoSource = VideoSource.VIMEO,
                 cookies_file: Optional[str] = None,
                 referer_url: Optional[str] = None):
        self.video_id = video_id
        self.video_hash = video_hash
        self.video_type = video_type
        self.password = password
        self.cookie_string = cookie_string
        self.original_url = original_url
        self.source = source
        self.cookies_file = cookies_file  # Path to Netscape cookies file (overrides cookie_string)
        self.referer_url = referer_url    # Source page URL used as HTTP Referer

    def get_url(self) -> str:
        """Get the appropriate URL for download."""
        # For direct stream URLs (m3u8, Kinescope, GetCourse, Skillshare), use the original URL
        if self.source in (VideoSource.DIRECT_STREAM, VideoSource.KINESCOPE, VideoSource.GETCOURSE, VideoSource.SKILLSHARE) and self.original_url:
            return self.original_url
        # For YouTube, use the standard watch URL
        if self.source == VideoSource.YOUTUBE:
            return f"https://www.youtube.com/watch?v={self.video_id}"
        if self.video_hash:
            return f"https://vimeo.com/{self.video_id}/{self.video_hash}"
        return f"https://vimeo.com/{self.video_id}"

    def is_direct_stream(self) -> bool:
        """Check if this is a direct stream URL (m3u8, Kinescope, GetCourse, Skillshare, etc.)."""
        return self.source in (VideoSource.DIRECT_STREAM, VideoSource.KINESCOPE, VideoSource.GETCOURSE, VideoSource.SKILLSHARE)
    
    def build_ytdlp_command(self, output_path: str = ".", use_aria2: bool = False, fast: bool = False, filename: str = None) -> List[str]:
        """Build yt-dlp command with appropriate flags."""

        url = self.get_url()
        referer = url

        # Use more concurrent fragments in fast mode
        concurrent = "32" if fast else "16"

        # Start with yt-dlp command (bundled or module)
        cmd = get_ytdlp_command() + [
            "-N", concurrent,  # Parallel fragments
            "--no-warnings",   # Hide warnings
            "--progress",      # Ensure progress bar shows
            "--newline",       # Output progress on new lines (cleaner)
            "--restrict-filenames",  # Sanitize filenames (remove special chars)
            "--replace-in-metadata", "title", r"[\n\r]", " ",  # Remove newlines from title
            "--replace-in-metadata", "title", r"\s+", " ",  # Collapse multiple spaces
            "--windows-filenames",  # Ensure Windows-safe filenames
        ]

        # Add ffmpeg path if bundled
        ffmpeg_path = get_ffmpeg_path()
        if ffmpeg_path:
            cmd.extend(["--ffmpeg-location", ffmpeg_path])
        
        # Add cookies: prefer a pre-built cookies file, then fall back to browser extraction
        if self.cookies_file:
            cmd.extend(["--cookies", self.cookies_file])
        elif self.cookie_string:
            cmd.extend(["--cookies-from-browser", self.cookie_string])
        else:
            cmd.append("--no-cookies-from-browser")

        # Add password if needed
        if self.password and self.video_type == VimeoType.PASSWORD_PROTECTED:
            cmd.extend(["--video-password", self.password])

        # Add referer
        if self.referer_url and self.is_direct_stream():
            # For direct streams (Mux, etc.), use the source page URL as referer
            cmd.extend(["--referer", self.referer_url])
        elif not self.is_direct_stream() and self.source != VideoSource.YOUTUBE:
            # For Vimeo, use the video URL itself as referer
            cmd.extend(["--referer", referer])

        # Quality and format selection
        if self.is_direct_stream():
            # For direct streams (m3u8, Kinescope), let yt-dlp figure it out
            cmd.extend([
                "--merge-output-format", "mp4",
            ])
        else:
            # For Vimeo/YouTube, select best video + best audio and merge
            # bv*+ba/b = best video + best audio, fallback to best combined
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
        else:
            # Native downloader works for both regular videos and HLS streams
            # and outputs progress that the progress bar can parse
            cmd.extend(["--downloader", "native"])

        # Put temp/part files in a subfolder to keep root clean
        cmd.extend(["--paths", f"temp:{output_path}/.downloading"])

        # Output path and filename
        if filename:
            # Sanitize user-specified filename (remove newlines, invalid chars)
            safe_filename = filename.replace('\n', ' ').replace('\r', ' ')
            safe_filename = safe_filename.replace('<', '').replace('>', '')
            safe_filename = safe_filename.replace(':', '-').replace('"', "'")
            safe_filename = safe_filename.replace('/', '-').replace('\\', '-')
            safe_filename = safe_filename.replace('|', '-').replace('?', '').replace('*', '')
            safe_filename = ' '.join(safe_filename.split())  # Collapse whitespace
            safe_filename = safe_filename.strip()
            cmd.extend(["-o", f"{output_path}/{safe_filename}.%(ext)s"])
        elif self.is_direct_stream():
            # Direct stream - use timestamp-based name with source prefix
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = self.source.value if self.source != VideoSource.DIRECT_STREAM else "stream"
            cmd.extend(["-o", f"{output_path}/{prefix}_{timestamp}.%(ext)s"])
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
