#!/usr/bin/env python3
"""
Video Downloader - GUI Application
Supports Vimeo, YouTube, Kinescope, GetCourse, and direct m3u8 streams.
"""

import sys


def main():
    """Launch the GUI application."""
    # Import here to avoid loading GUI modules when not needed
    from gui.app import MainWindow

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
