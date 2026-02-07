"""
Command construction for different download methods.
"""

from typing import List, Optional
from .detector import VimeoType, VideoSource
from .runtime import ytdlp_cmd


class CommandBuilder:
    """Build appropriate download commands based on video type."""

    def __init__(self, video_id: str, video_hash: Optional[str],
                 video_type: VimeoType, password: Optional[str] = None,
                 cookie_string: Optional[str] = None, original_url: Optional[str] = None,
                 source: VideoSource = VideoSource.VIMEO):
        self.video_id = video_id
        self.video_hash = video_hash
        self.video_type = video_type
        self.password = password
        self.cookie_string = cookie_string
        self.original_url = original_url
        self.source = source

    def get_url(self) -> str:
        """Get the appropriate URL for download."""
        # For direct stream URLs (m3u8, Kinescope, GetCourse), use the original URL
        if self.source in (VideoSource.DIRECT_STREAM, VideoSource.KINESCOPE, VideoSource.GETCOURSE) and self.original_url:
            return self.original_url
        # For YouTube, use the standard watch URL
        if self.source == VideoSource.YOUTUBE:
            return f"https://www.youtube.com/watch?v={self.video_id}"
        if self.video_hash:
            return f"https://vimeo.com/{self.video_id}/{self.video_hash}"
        return f"https://vimeo.com/{self.video_id}"

    def is_direct_stream(self) -> bool:
        """Check if this is a direct stream URL (m3u8, Kinescope, GetCourse, etc.)."""
        return self.source in (VideoSource.DIRECT_STREAM, VideoSource.KINESCOPE, VideoSource.GETCOURSE)
    
    def build_ytdlp_command(self, output_path: str = ".", use_aria2: bool = False, fast: bool = False, filename: str = None) -> List[str]:
        """Build yt-dlp command with appropriate flags."""

        url = self.get_url()
        referer = url

        # Use more concurrent fragments in fast mode
        concurrent = "32" if fast else "16"

        cmd = [
            *ytdlp_cmd(),
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

        # Add referer (skip for direct streams and YouTube)
        if not self.is_direct_stream() and self.source != VideoSource.YOUTUBE:
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
            # User specified filename
            cmd.extend(["-o", f"{output_path}/{filename}.%(ext)s"])
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
