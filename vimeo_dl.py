#!/usr/bin/env python3
"""
Vimeo Video Downloader - CLI Tool
Based on methods from: https://gist.github.com/devinschumacher/8024bc4693d79aef641b2c281e45d6cb
"""

import click
from rich.console import Console
from core.downloader import VimeoDownloader

console = Console()


@click.command()
@click.argument('url')
@click.option('--password', '-p', help='Password for password-protected videos')
@click.option('--output', '-o', default='.', help='Output directory (default: current directory)')
@click.option('--name', '-n', default=None, help='Output filename (without extension)')
@click.option('--browser', '-b', default='chrome', help='Browser to extract cookies from (chrome/firefox/edge)')
@click.option('--profile', help='Browser profile name (e.g., "Profile 1", "Default")')
@click.option('--aria2', is_flag=True, help='Use aria2c for faster downloads')
@click.option('--fast', '-f', is_flag=True, help='Use maximum concurrent downloads (32 fragments)')
@click.option('--dry-run', is_flag=True, help='Show command without executing')
@click.option('--list-formats', '-F', is_flag=True, help='List available formats without downloading')
@click.option('--no-cookies', is_flag=True, help='Skip cookie extraction (for direct m3u8 URLs or public videos)')
@click.option('--no-progress', is_flag=True, help='Disable rich progress bar, use yt-dlp native output')
def main(url, password, output, name, browser, profile, aria2, fast, dry_run, list_formats, no_cookies, no_progress):
    """
    Download Vimeo videos with automatic type detection and authentication.
    
    Examples:
    
        python vimeo_dl.py https://vimeo.com/123456789
        
        python vimeo_dl.py https://vimeo.com/123456789/abcdef123 --password mypass
        
        python vimeo_dl.py https://player.vimeo.com/video/123456789 --aria2
    """
    
    console.print("[bold cyan]Vimeo Video Downloader[/bold cyan]\n")
    
    # Create downloader
    downloader = VimeoDownloader(
        url=url,
        password=password,
        browser=browser,
        profile=profile,
        skip_cookies=no_cookies
    )
    
    # Analyse
    if not downloader.analyze():
        return
    
    # List formats or download
    if list_formats:
        downloader.list_formats()
    else:
        downloader.download(output, aria2, dry_run, fast, name, show_progress=not no_progress)


if __name__ == '__main__':
    main()
