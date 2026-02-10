"""
yt-dlp Download Module — download video, audio, subtitles, and thumbnails
from YouTube, TikTok, Twitter, and 1000+ sites.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from peg_this.utils.validation import (
    check_output_file,
    format_duration,
    press_continue,
)

console = Console()


# =============================================================================
# DEPENDENCY CHECK
# =============================================================================

def check_ytdlp_installed():
    """Check if yt-dlp is installed and accessible."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return None


def show_install_instructions():
    """Show platform-specific yt-dlp install instructions."""
    console.print("[bold red]yt-dlp is not installed.[/bold red]\n")
    console.print("[bold cyan]Install yt-dlp:[/bold cyan]")

    system = platform.system()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="cyan")
    table.add_column()

    if system == "Darwin":
        table.add_row("brew", "brew install yt-dlp")
        table.add_row("pip", "pip install yt-dlp")
    elif system == "Windows":
        table.add_row("scoop", "scoop install yt-dlp")
        table.add_row("winget", "winget install yt-dlp")
        table.add_row("pip", "pip install yt-dlp")
    else:
        table.add_row("apt", "sudo apt install yt-dlp")
        table.add_row("pip", "pip install yt-dlp")

    table.add_row("", "")
    table.add_row("optional", "pip install peg_this[download]")

    console.print(table)


# =============================================================================
# URL VALIDATION & METADATA
# =============================================================================

def validate_url_and_get_metadata(url):
    """Validate URL and extract metadata using yt-dlp --dump-json."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--playlist-items", "1",
             "--no-warnings", "--no-download", url],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "Private video" in stderr or "private" in stderr.lower():
                console.print("[bold red]This video is private.[/bold red]")
                console.print("[yellow]Tip: Use a cookies.txt file to access private content.[/yellow]")
            elif "geo" in stderr.lower() or "blocked" in stderr.lower():
                console.print("[bold red]This video is geo-restricted.[/bold red]")
                console.print("[yellow]Tip: Use a proxy or VPN.[/yellow]")
            elif "removed" in stderr.lower() or "deleted" in stderr.lower() or "not available" in stderr.lower():
                console.print("[bold red]This video has been removed or is unavailable.[/bold red]")
            elif "age" in stderr.lower():
                console.print("[bold red]This video is age-restricted.[/bold red]")
                console.print("[yellow]Tip: Provide a cookies.txt file from a logged-in browser session.[/yellow]")
            else:
                console.print(f"[bold red]Could not access URL.[/bold red]")
                console.print(f"[dim]{stderr[:300]}[/dim]")
            return None

        metadata = json.loads(result.stdout)
        return metadata

    except subprocess.TimeoutExpired:
        console.print("[bold red]Request timed out. Check your connection and try again.[/bold red]")
        return None
    except json.JSONDecodeError:
        console.print("[bold red]Could not parse video metadata.[/bold red]")
        return None
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        return None


def _format_number(n):
    """Format large numbers with K/M suffix."""
    if n is None:
        return None
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _format_filesize(bytes_val):
    """Format bytes into human-readable size."""
    if not bytes_val:
        return None
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def _format_date(date_str):
    """Format YYYYMMDD into readable date."""
    if not date_str or len(date_str) != 8:
        return None
    try:
        return f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except Exception:
        return date_str


def display_metadata(metadata):
    """Display rich video/playlist metadata."""
    # ── Basic info ──
    info = Table(show_header=False, box=None, padding=(0, 1))
    info.add_column(style="dim", min_width=14)
    info.add_column()

    title = metadata.get("title", "Unknown")
    channel = metadata.get("channel", metadata.get("uploader", "Unknown"))
    verified = metadata.get("channel_is_verified", False)
    channel_display = f"{channel} [cyan]✓[/cyan]" if verified else channel

    info.add_row("Title:", f"[bold]{title}[/bold]")
    info.add_row("Channel:", channel_display)

    upload_date = _format_date(metadata.get("upload_date"))
    if upload_date:
        info.add_row("Uploaded:", upload_date)

    duration = metadata.get("duration")
    if duration:
        info.add_row("Duration:", format_duration(duration))

    categories = metadata.get("categories")
    if categories:
        info.add_row("Category:", ", ".join(categories))

    # ── Engagement stats ──
    stats_parts = []
    view_count = metadata.get("view_count")
    like_count = metadata.get("like_count")
    comment_count = metadata.get("comment_count")

    if view_count:
        stats_parts.append(f"[bold]{_format_number(view_count)}[/bold] views")
    if like_count:
        stats_parts.append(f"[bold]{_format_number(like_count)}[/bold] likes")
    if comment_count:
        stats_parts.append(f"[bold]{_format_number(comment_count)}[/bold] comments")
    if stats_parts:
        info.add_row("Stats:", "  ".join(stats_parts))

    # ── Technical details (best format) ──
    width = metadata.get("width")
    height = metadata.get("height")
    fps = metadata.get("fps")
    dynamic_range = metadata.get("dynamic_range")

    if width and height:
        res_str = f"{width}x{height}"
        if fps:
            res_str += f" @ {fps}fps"
        if dynamic_range and dynamic_range != "SDR":
            res_str += f"  [magenta]{dynamic_range}[/magenta]"
        info.add_row("Best Quality:", res_str)

    vcodec = metadata.get("vcodec")
    acodec = metadata.get("acodec")
    if vcodec and vcodec != "none":
        codec_str = vcodec.split(".")[0]
        if acodec and acodec != "none":
            codec_str += f" + {acodec.split('.')[0]}"
        info.add_row("Codecs:", codec_str)

    filesize = metadata.get("filesize_approx") or metadata.get("filesize")
    if filesize:
        info.add_row("Est. Size:", f"~{_format_filesize(filesize)}")

    # ── Available formats from formats list ──
    formats = metadata.get("formats", [])
    if formats:
        resolutions = sorted(set(
            f.get("height") for f in formats if f.get("height") and f.get("vcodec", "none") != "none"
        ), reverse=True)
        if resolutions:
            res_labels = []
            for h in resolutions:
                label = f"{h}p"
                if h >= 2160:
                    label += " [yellow]4K[/yellow]"
                elif h >= 1440:
                    label += " [cyan]2K[/cyan]"
                res_labels.append(label)
            info.add_row("Available:", ", ".join(res_labels))

        audio_fmts = [
            f for f in formats
            if f.get("acodec", "none") != "none" and f.get("vcodec", "none") == "none"
        ]
        if audio_fmts:
            best_abr = max((f.get("abr", 0) or 0 for f in audio_fmts), default=0)
            audio_codecs = sorted(set(
                f.get("acodec", "").split(".")[0] for f in audio_fmts if f.get("acodec")
            ))
            audio_str = ", ".join(audio_codecs)
            if best_abr:
                audio_str += f"  (up to {int(best_abr)}kbps)"
            info.add_row("Audio:", audio_str)

    # ── Availability & flags ──
    flags = []
    availability = metadata.get("availability")
    if availability and availability != "public":
        flags.append(f"[yellow]{availability}[/yellow]")
    if metadata.get("is_live"):
        flags.append("[red]LIVE[/red]")
    if metadata.get("was_live"):
        flags.append("[dim]was live[/dim]")
    age_limit = metadata.get("age_limit", 0)
    if age_limit:
        flags.append(f"[yellow]{age_limit}+[/yellow]")
    if flags:
        info.add_row("Flags:", "  ".join(flags))

    console.print(Panel(info, title="[bold cyan]Video Info[/bold cyan]", border_style="cyan"))


def get_url_from_user():
    """Prompt user for a URL, validate it, and return (url, metadata)."""
    while True:
        url = questionary.text("Enter URL:").ask()
        if not url:
            return None, None

        url = url.strip()
        if not url.startswith(("http://", "https://", "www.")):
            console.print("[bold red]Please enter a valid URL.[/bold red]")
            continue

        with console.status("[cyan]Fetching video info...[/cyan]", spinner="dots"):
            metadata = validate_url_and_get_metadata(url)

        if metadata:
            display_metadata(metadata)
            return url, metadata

        retry = questionary.confirm("Try a different URL?", default=True).ask()
        if not retry:
            return None, None


# =============================================================================
# COMMAND BUILDING
# =============================================================================

def build_ytdlp_command(url, options):
    """Assemble the full yt-dlp command list from collected options."""
    cmd = ["yt-dlp", "--newline", "--no-warnings"]

    # Format selection
    if options.get("format"):
        cmd.extend(["-f", options["format"]])

    # Merge output format (e.g. mp4 instead of webm)
    if options.get("merge_output_format"):
        cmd.extend(["--merge-output-format", options["merge_output_format"]])

    # Output template
    template = options.get("output_template", "%(title)s.%(ext)s")
    cmd.extend(["-o", template])

    # Audio extraction
    if options.get("extract_audio"):
        cmd.append("-x")
        if options.get("audio_format"):
            cmd.extend(["--audio-format", options["audio_format"]])
        if options.get("audio_quality"):
            cmd.extend(["--audio-quality", options["audio_quality"]])

    # Playlist range
    if options.get("playlist_items"):
        cmd.extend(["--playlist-items", options["playlist_items"]])

    # Subtitles
    if options.get("write_subs"):
        cmd.append("--write-subs")
    if options.get("write_auto_subs"):
        cmd.append("--write-auto-subs")
    if options.get("sub_langs"):
        cmd.extend(["--sub-langs", options["sub_langs"]])
    if options.get("sub_format"):
        cmd.extend(["--sub-format", options["sub_format"]])
    if options.get("skip_download"):
        cmd.append("--skip-download")

    # Thumbnail
    if options.get("write_thumbnail"):
        cmd.append("--write-thumbnail")
    if options.get("convert_thumbnails"):
        cmd.extend(["--convert-thumbnails", options["convert_thumbnails"]])

    # Embed options
    if options.get("embed_thumbnail"):
        cmd.append("--embed-thumbnail")
    if options.get("embed_metadata"):
        cmd.append("--embed-metadata")
    if options.get("embed_subs"):
        cmd.append("--embed-subs")
    if options.get("embed_chapters"):
        cmd.append("--embed-chapters")

    # SponsorBlock
    if options.get("sponsorblock_remove"):
        cmd.extend(["--sponsorblock-remove", options["sponsorblock_remove"]])

    # Speed limit
    if options.get("rate_limit"):
        cmd.extend(["-r", options["rate_limit"]])

    # Time range / download sections
    if options.get("download_sections"):
        cmd.extend(["--download-sections", options["download_sections"]])
        cmd.append("--force-keyframes-at-cuts")

    # Cookies
    if options.get("cookies"):
        cmd.extend(["--cookies", options["cookies"]])

    # Proxy
    if options.get("proxy"):
        cmd.extend(["--proxy", options["proxy"]])

    # Retry
    cmd.extend(["--retries", "3", "--fragment-retries", "3"])

    cmd.append(url)
    return cmd


# =============================================================================
# PROGRESS DISPLAY
# =============================================================================

def run_with_progress(cmd, playlist_total=None):
    """Run yt-dlp command and display progress using Rich."""
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        console.print("[bold red]yt-dlp not found. Is it installed?[/bold red]")
        return False

    download_re = re.compile(
        r"\[download\]\s+(\d+\.?\d*)%\s+of\s+~?\s*([\d.]+\w+)"
        r"(?:\s+at\s+([\d.]+\w+/s))?"
        r"(?:\s+ETA\s+([\d:]+))?"
    )
    playlist_re = re.compile(r"\[download\]\s+Downloading item (\d+) of (\d+)")
    destination_re = re.compile(r"\[download\]\s+Destination:\s+(.+)")
    merge_re = re.compile(r'\[Merger\]\s+Merging formats into "(.+)"')
    already_re = re.compile(r"\[download\]\s+(.+) has already been downloaded")

    output_file = None
    final_file = None
    success = False
    current_playlist_item = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        TextColumn("{task.fields[status]}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Downloading...", total=100, status="")

        for line in process.stdout:
            line = line.rstrip()

            # Playlist item counter
            pl_match = playlist_re.match(line)
            if pl_match:
                current_playlist_item = int(pl_match.group(1))
                total = int(pl_match.group(2))
                progress.update(task, description=f"[{current_playlist_item}/{total}]")
                continue

            # Destination file
            dest_match = destination_re.match(line)
            if dest_match:
                output_file = dest_match.group(1)
                continue

            # Already downloaded
            already_match = already_re.match(line)
            if already_match:
                output_file = already_match.group(1)
                success = True
                continue

            # Download progress
            dl_match = download_re.match(line)
            if dl_match:
                pct = float(dl_match.group(1))
                size = dl_match.group(2)
                speed = dl_match.group(3) or ""
                eta = dl_match.group(4) or ""

                status_parts = [size]
                if speed:
                    status_parts.append(speed)
                if eta:
                    status_parts.append(f"ETA {eta}")

                progress.update(task, completed=pct, status=" | ".join(status_parts))
                continue

            # Merge — captures the final output filename
            merge_match = merge_re.match(line)
            if merge_match:
                final_file = merge_match.group(1)
                progress.update(task, description="Merging...", completed=100, status="")
                continue

    process.wait()
    success = process.returncode == 0 or success

    # Prefer the merged filename over intermediate stream filenames
    return success, (final_file or output_file)


# =============================================================================
# QUALITY & FORMAT SELECTION
# =============================================================================

QUALITY_MAP = {
    "Best Available": "bestvideo+bestaudio/best",
    "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1080p (Full HD)": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p (HD)": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p (SD)": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p (Low)": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}

AUDIO_FORMAT_MAP = {
    "MP3 (Most compatible)": "mp3",
    "FLAC (Lossless)": "flac",
    "WAV (Uncompressed)": "wav",
    "AAC": "aac",
    "Opus (Smallest)": "opus",
    "M4A": "m4a",
}

AUDIO_QUALITY_MAP = {
    "Best": "0",
    "320kbps": "320K",
    "256kbps": "256K",
    "192kbps": "192K",
    "128kbps": "128K",
}


CONTAINER_MAP = {
    "MP4 (Recommended)": "mp4",
    "MKV (Matroska)": "mkv",
    "WebM (Original)": "webm",
}


def select_video_quality():
    """Let user pick video quality and container format, returns (format_str, container)."""
    choices = list(QUALITY_MAP.keys()) + ["List All Formats"]
    quality = questionary.select("Select quality:", choices=choices).ask()
    if quality is None:
        return None, None

    if quality == "List All Formats":
        console.print("[dim]Use the format code from yt-dlp's format list.[/dim]")
        fmt = questionary.text("Enter format code (e.g. 137+140):").ask()
        if not fmt:
            return None, None
        container = questionary.select("Output container:", choices=list(CONTAINER_MAP.keys())).ask()
        return (fmt, CONTAINER_MAP.get(container, "mp4")) if container else (None, None)

    container = questionary.select("Output format:", choices=list(CONTAINER_MAP.keys())).ask()
    if container is None:
        return None, None

    return QUALITY_MAP[quality], CONTAINER_MAP[container]


def select_audio_format():
    """Let user pick audio format."""
    fmt = questionary.select(
        "Select audio format:",
        choices=list(AUDIO_FORMAT_MAP.keys()),
    ).ask()
    if fmt is None:
        return None
    return AUDIO_FORMAT_MAP[fmt]


def select_audio_quality():
    """Let user pick audio quality."""
    q = questionary.select(
        "Select audio quality:",
        choices=list(AUDIO_QUALITY_MAP.keys()),
    ).ask()
    if q is None:
        return None
    return AUDIO_QUALITY_MAP[q]


# =============================================================================
# ADVANCED OPTIONS
# =============================================================================

def configure_advanced_options(options):
    """Prompt for advanced download options, mutating the options dict."""
    show = questionary.select(
        "Configure advanced options?",
        choices=[
            "No, download now (Recommended)",
            "Yes, show options",
        ],
    ).ask()

    if show is None or "No" in show:
        return

    # SponsorBlock
    sb = questionary.select(
        "SponsorBlock:",
        choices=[
            "Off",
            "Skip sponsors only",
            "Skip all (sponsor, intro, outro, selfpromo)",
        ],
    ).ask()
    if sb and "sponsors only" in sb:
        options["sponsorblock_remove"] = "sponsor"
    elif sb and "Skip all" in sb:
        options["sponsorblock_remove"] = "all"

    # Speed limit
    speed = questionary.select(
        "Speed limit:",
        choices=["Unlimited", "1 MB/s", "5 MB/s", "10 MB/s", "Custom"],
    ).ask()
    speed_map = {"1 MB/s": "1M", "5 MB/s": "5M", "10 MB/s": "10M"}
    if speed and speed in speed_map:
        options["rate_limit"] = speed_map[speed]
    elif speed == "Custom":
        custom = questionary.text("Enter speed limit (e.g. 500K, 2M):").ask()
        if custom:
            options["rate_limit"] = custom

    # Time range
    time_range = questionary.select(
        "Time range:",
        choices=["Full video", "Custom start-end"],
    ).ask()
    if time_range == "Custom start-end":
        start = questionary.text("Start time (e.g. 0:30 or 30):").ask()
        end = questionary.text("End time (e.g. 2:00 or 120):").ask()
        if start and end:
            options["download_sections"] = f"*{start}-{end}"

    # Embed metadata
    embed_meta = questionary.confirm("Embed metadata (title, artist, date)?", default=True).ask()
    if embed_meta:
        options["embed_metadata"] = True

    # Embed thumbnail
    embed_thumb = questionary.confirm("Embed thumbnail as cover art?", default=False).ask()
    if embed_thumb:
        options["embed_thumbnail"] = True

    # Embed subtitles
    embed_subs = questionary.select(
        "Embed subtitles:",
        choices=["Off", "Auto-generated", "Specific language"],
    ).ask()
    if embed_subs == "Auto-generated":
        options["embed_subs"] = True
        options["write_auto_subs"] = True
        options["sub_langs"] = "en"
    elif embed_subs == "Specific language":
        lang = questionary.text("Language code (e.g. en, es, fr):").ask()
        if lang:
            options["embed_subs"] = True
            options["write_subs"] = True
            options["sub_langs"] = lang

    # Embed chapters
    embed_ch = questionary.confirm("Embed chapters?", default=True).ask()
    if embed_ch:
        options["embed_chapters"] = True

    # Cookies file
    cookies = questionary.select(
        "Cookies file:",
        choices=["None", "Enter path to cookies.txt"],
    ).ask()
    if cookies and "Enter" in cookies:
        path = questionary.text("Path to cookies.txt:").ask()
        if path and os.path.isfile(path):
            options["cookies"] = path
        elif path:
            console.print("[yellow]File not found, skipping cookies.[/yellow]")

    # Proxy
    proxy = questionary.select(
        "Proxy:",
        choices=["None", "Enter proxy URL"],
    ).ask()
    if proxy and "Enter" in proxy:
        proxy_url = questionary.text("Proxy URL (e.g. socks5://127.0.0.1:1080):").ask()
        if proxy_url:
            options["proxy"] = proxy_url

    # Output template
    tmpl = questionary.select(
        "Output filename template:",
        choices=[
            "Default (%(title)s.%(ext)s)",
            "Custom",
        ],
    ).ask()
    if tmpl == "Custom":
        custom_tmpl = questionary.text(
            "Template (yt-dlp syntax):",
            default="%(title)s.%(ext)s",
        ).ask()
        if custom_tmpl:
            options["output_template"] = custom_tmpl


# =============================================================================
# DOWNLOAD MODES
# =============================================================================

def download_single_video(url, metadata):
    """Download a single video."""
    fmt, container = select_video_quality()
    if fmt is None:
        return

    options = {"format": fmt, "merge_output_format": container}
    configure_advanced_options(options)

    cmd = build_ytdlp_command(url, options)
    console.print()
    success, output_file = run_with_progress(cmd)

    if success:
        console.print(f"\n[bold green]Download complete![/bold green]")
        if output_file:
            console.print(f"[green]Saved: {output_file}[/green]")
        post_download_actions(output_file)
    else:
        console.print("\n[bold red]Download failed.[/bold red]")
        press_continue()


def download_audio_only(url, metadata):
    """Download audio only."""
    audio_fmt = select_audio_format()
    if audio_fmt is None:
        return

    audio_qual = select_audio_quality()
    if audio_qual is None:
        return

    options = {
        "extract_audio": True,
        "audio_format": audio_fmt,
        "audio_quality": audio_qual,
        "format": "bestaudio/best",
    }

    # Optional: embed cover art and metadata
    embed_thumb = questionary.confirm("Embed thumbnail as cover art?", default=True).ask()
    if embed_thumb:
        options["embed_thumbnail"] = True

    embed_meta = questionary.confirm("Embed metadata?", default=True).ask()
    if embed_meta:
        options["embed_metadata"] = True

    cmd = build_ytdlp_command(url, options)
    console.print()
    success, output_file = run_with_progress(cmd)

    if success:
        console.print(f"\n[bold green]Audio download complete![/bold green]")
        if output_file:
            console.print(f"[green]Saved: {output_file}[/green]")
    else:
        console.print("\n[bold red]Download failed.[/bold red]")

    press_continue()


def download_playlist(url, metadata):
    """Download a playlist."""
    # Get playlist info
    with console.status("[cyan]Fetching playlist info...[/cyan]", spinner="dots"):
        try:
            result = subprocess.run(
                ["yt-dlp", "--flat-playlist", "--dump-json",
                 "--no-warnings", url],
                capture_output=True, text=True, timeout=120,
            )
            entries = []
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            entries = []

    video_count = len(entries) if entries else "unknown"
    playlist_title = metadata.get("playlist_title", metadata.get("title", "Playlist"))
    console.print(f"[bold cyan]Playlist: {playlist_title}[/bold cyan]")
    console.print(f"[dim]Videos: {video_count}[/dim]")

    # Range selection
    range_choice = questionary.select(
        "Which videos to download?",
        choices=["All", "First N", "Range (e.g. 5-10)", "Specific numbers (e.g. 1,3,5)"],
    ).ask()
    if range_choice is None:
        return

    options = {}

    if range_choice == "First N":
        n = questionary.text("How many videos?").ask()
        if n and n.isdigit():
            options["playlist_items"] = f"1:{n}"
        else:
            return
    elif "Range" in range_choice:
        r = questionary.text("Enter range (e.g. 5-10):").ask()
        if r:
            options["playlist_items"] = r.replace("-", ":")
        else:
            return
    elif "Specific" in range_choice:
        nums = questionary.text("Enter video numbers (e.g. 1,3,5,8):").ask()
        if nums:
            options["playlist_items"] = nums
        else:
            return

    # Quality
    fmt, container = select_video_quality()
    if fmt is None:
        return
    options["format"] = fmt
    options["merge_output_format"] = container

    # Numbering prefix
    number_prefix = questionary.confirm("Add numbering prefix to filenames?", default=True).ask()
    if number_prefix:
        options["output_template"] = "%(playlist_index)s - %(title)s.%(ext)s"

    cmd = build_ytdlp_command(url, options)
    console.print()
    success, output_file = run_with_progress(cmd, playlist_total=video_count)

    if success:
        console.print(f"\n[bold green]Playlist download complete![/bold green]")
    else:
        console.print("\n[bold red]Some downloads may have failed.[/bold red]")

    press_continue()


def download_subtitles(url, metadata):
    """Download subtitles only."""
    lang = questionary.select(
        "Subtitle language:",
        choices=[
            "English", "Spanish", "French", "German",
            "Japanese", "Korean", "All available", "Custom language code",
        ],
    ).ask()
    if lang is None:
        return

    lang_map = {
        "English": "en", "Spanish": "es", "French": "fr",
        "German": "de", "Japanese": "ja", "Korean": "ko",
        "All available": "all",
    }

    if lang == "Custom language code":
        lang_code = questionary.text("Enter language code (e.g. pt, zh, ar):").ask()
        if not lang_code:
            return
    else:
        lang_code = lang_map[lang]

    sub_fmt = questionary.select(
        "Subtitle format:",
        choices=["SRT", "VTT", "ASS"],
    ).ask()
    if sub_fmt is None:
        return

    include_auto = questionary.confirm(
        "Include auto-generated subtitles?", default=True
    ).ask()

    options = {
        "skip_download": True,
        "write_subs": True,
        "sub_langs": lang_code,
        "sub_format": sub_fmt.lower(),
    }
    if include_auto:
        options["write_auto_subs"] = True

    cmd = build_ytdlp_command(url, options)
    console.print()
    success, output_file = run_with_progress(cmd)

    if success:
        console.print(f"\n[bold green]Subtitles downloaded![/bold green]")
    else:
        console.print("\n[bold red]Subtitle download failed. Subtitles may not be available.[/bold red]")

    press_continue()


def download_thumbnail(url, metadata):
    """Download thumbnail only."""
    options = {
        "skip_download": True,
        "write_thumbnail": True,
        "convert_thumbnails": "jpg",
    }

    cmd = build_ytdlp_command(url, options)
    console.print()
    success, output_file = run_with_progress(cmd)

    if success:
        console.print(f"\n[bold green]Thumbnail saved![/bold green]")
        if output_file:
            console.print(f"[green]File: {output_file}[/green]")
    else:
        console.print("\n[bold red]Thumbnail download failed.[/bold red]")

    press_continue()


# =============================================================================
# POST-DOWNLOAD ACTIONS
# =============================================================================

def post_download_actions(file_path):
    """Offer to process the downloaded file with existing features."""
    if not file_path or not os.path.isfile(file_path):
        press_continue()
        return

    action = questionary.select(
        "What next?",
        choices=[
            "Done - return to menu",
            "Trim video",
            "Convert format",
            "Compress",
            "Extract audio",
            "Generate subtitles (Whisper)",
            "Open file location",
        ],
    ).ask()

    if action is None or "Done" in action:
        return

    if "Open file location" in action:
        folder = os.path.dirname(os.path.abspath(file_path))
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", folder])
            elif platform.system() == "Windows":
                subprocess.run(["explorer", folder])
            else:
                subprocess.run(["xdg-open", folder])
        except Exception:
            console.print(f"[dim]File location: {folder}[/dim]")
        return

    # Lazy imports to avoid circular dependencies
    if "Trim" in action:
        from peg_this.features.trim import trim_video
        trim_video(file_path)
    elif "Convert" in action:
        from peg_this.features.convert import convert_file
        convert_file(file_path)
    elif "Compress" in action:
        from peg_this.features.compress import compress_video
        compress_video(file_path)
    elif "Extract audio" in action:
        from peg_this.features.audio import extract_audio
        extract_audio(file_path)
    elif "subtitles" in action.lower():
        from peg_this.features.subtitle import generate_subtitles
        generate_subtitles(file_path)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def download_media():
    """Main download menu — entry point from peg_this main menu."""
    version = check_ytdlp_installed()
    if not version:
        show_install_instructions()
        press_continue()
        return

    console.print(f"[dim]yt-dlp v{version}[/dim]")

    action = questionary.select(
        "What would you like to download?",
        choices=[
            "Single Video",
            "Audio Only",
            "Playlist",
            "Subtitles Only",
            "Thumbnail Only",
            questionary.Separator(),
            "← Back",
        ],
    ).ask()

    if action is None or "Back" in action:
        return

    url, metadata = get_url_from_user()
    if not url:
        return

    if action == "Single Video":
        download_single_video(url, metadata)
    elif action == "Audio Only":
        download_audio_only(url, metadata)
    elif action == "Playlist":
        download_playlist(url, metadata)
    elif action == "Subtitles Only":
        download_subtitles(url, metadata)
    elif action == "Thumbnail Only":
        download_thumbnail(url, metadata)


def download_url(url):
    """Direct download entry point — validates URL and goes straight to single video."""
    version = check_ytdlp_installed()
    if not version:
        show_install_instructions()
        return

    console.print(f"[dim]yt-dlp v{version}[/dim]")

    url = url.strip()
    if not url.startswith(("http://", "https://", "www.")):
        console.print(f"[bold red]Invalid URL: {url}[/bold red]")
        return

    with console.status("[cyan]Fetching video info...[/cyan]", spinner="dots"):
        metadata = validate_url_and_get_metadata(url)

    if not metadata:
        return

    display_metadata(metadata)
    download_single_video(url, metadata)


def download_url_quick(url):
    """Zero-prompt download — best quality MP4, no questions asked."""
    version = check_ytdlp_installed()
    if not version:
        show_install_instructions()
        return

    console.print(f"[dim]yt-dlp v{version}[/dim]")

    url = url.strip()
    if not url.startswith(("http://", "https://", "www.")):
        console.print(f"[bold red]Invalid URL: {url}[/bold red]")
        return

    with console.status("[cyan]Fetching video info...[/cyan]", spinner="dots"):
        metadata = validate_url_and_get_metadata(url)

    if not metadata:
        return

    display_metadata(metadata)

    options = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
    }

    cmd = build_ytdlp_command(url, options)
    console.print()
    success, output_file = run_with_progress(cmd)

    if success:
        console.print(f"\n[bold green]Download complete![/bold green]")
        if output_file:
            console.print(f"[green]Saved: {output_file}[/green]")
    else:
        console.print("\n[bold red]Download failed.[/bold red]")
