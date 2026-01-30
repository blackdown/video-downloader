#!/usr/bin/env python3
"""
Video Downloader - CLI Tool
Supports Vimeo, YouTube, Kinescope, GetCourse, and direct m3u8 streams.
"""

import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from core.downloader import VimeoDownloader

console = Console()


def download_single(url: str, password: str, output: str, name: str, browser: str,
                    profile: str, aria2: bool, fast: bool, dry_run: bool,
                    list_formats: bool, no_cookies: bool, no_progress: bool) -> bool:
    """Download a single video. Returns True on success."""

    downloader = VimeoDownloader(
        url=url,
        password=password,
        browser=browser,
        profile=profile,
        skip_cookies=no_cookies
    )

    if not downloader.analyze():
        return False

    if list_formats:
        return downloader.list_formats()
    else:
        return downloader.download(output, aria2, dry_run, fast, name, show_progress=not no_progress)


def load_batch_file(batch_path: str) -> list:
    """Load URLs from a batch file. Skips empty lines and comments (#)."""
    urls = []
    path = Path(batch_path)

    if not path.exists():
        console.print(f"[red]✗ Batch file not found: {batch_path}[/red]")
        return []

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                urls.append(line)

    return urls


@click.command()
@click.argument('url', required=False)
@click.option('--batch', '-B', 'batch_file', help='Batch file with URLs (one per line)')
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
def main(url, batch_file, password, output, name, browser, profile, aria2, fast, dry_run, list_formats, no_cookies, no_progress):
    """
    Download videos from Vimeo, YouTube, Kinescope, GetCourse, or direct m3u8 streams.

    Examples:

        video_dl https://vimeo.com/123456789

        video_dl https://www.youtube.com/watch?v=dQw4w9WgXcQ --fast

        video_dl --batch urls.txt --no-cookies

        video_dl "https://example.com/video.m3u8" --no-cookies -n "My Video"
    """

    console.print("[bold cyan]Video Downloader[/bold cyan]\n")

    # Validate arguments
    if not url and not batch_file:
        console.print("[red]✗ Please provide a URL or use --batch with a file[/red]")
        return

    if url and batch_file:
        console.print("[yellow]⚠ Both URL and --batch provided. Using batch file.[/yellow]\n")

    # Batch mode
    if batch_file:
        urls = load_batch_file(batch_file)
        if not urls:
            console.print("[red]✗ No valid URLs found in batch file[/red]")
            return

        total = len(urls)
        console.print(f"[cyan]Loaded {total} URLs from batch file[/cyan]\n")

        succeeded = 0
        failed = 0

        for i, batch_url in enumerate(urls, 1):
            console.print(Panel(f"[bold]Video {i}/{total}[/bold]", style="blue"))

            # Don't use custom name in batch mode (would overwrite)
            success = download_single(
                batch_url, password, output, None, browser, profile,
                aria2, fast, dry_run, list_formats, no_cookies, no_progress
            )

            if success:
                succeeded += 1
            else:
                failed += 1

            console.print()  # Blank line between videos

        # Summary
        console.print(Panel(
            f"[green]✓ Succeeded: {succeeded}[/green]  [red]✗ Failed: {failed}[/red]  Total: {total}",
            title="Batch Complete",
            style="cyan"
        ))

    # Single URL mode
    else:
        download_single(
            url, password, output, name, browser, profile,
            aria2, fast, dry_run, list_formats, no_cookies, no_progress
        )


if __name__ == '__main__':
    main()
