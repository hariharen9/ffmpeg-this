import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command
from peg_this.utils.validation import (
    validate_input_file, check_output_file, get_video_duration,
    format_duration, check_disk_space, press_continue
)

console = Console()


def compress_video(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    try:
        probe = ffmpeg.probe(file_path)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        duration = float(probe['format'].get('duration', 0))
    except Exception as e:
        console.print(f"[bold red]Error reading file: {e}[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Current size: {file_size_mb:.1f} MB | Duration: {format_duration(duration)}[/dim]")

    method = questionary.select(
        "How would you like to compress?",
        choices=[
            "Target file size (e.g., 25 MB for Discord)",
            "Quality preset (CRF)",
            "← Back"
        ]
    ).ask()

    if method == "← Back" or method is None:
        return

    output_file = f"{Path(file_path).stem}_compressed{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    if method == "Target file size (e.g., 25 MB for Discord)":
        target_size = questionary.text(
            "Enter target size in MB:",
            default="25"
        ).ask()

        if not target_size:
            return

        try:
            target_mb = float(target_size)
            if target_mb <= 0:
                console.print("[bold red]Target size must be positive.[/bold red]")
                press_continue()
                return
        except ValueError:
            console.print("[bold red]Invalid size value.[/bold red]")
            press_continue()
            return

        if target_mb >= file_size_mb:
            console.print(f"[yellow]Target size ({target_mb} MB) is larger than current size ({file_size_mb:.1f} MB).[/yellow]")
            if not questionary.confirm("Continue anyway?", default=False).ask():
                return

        target_bits = target_mb * 8 * 1024 * 1024
        audio_bitrate = 128 * 1024  # 128 kbps for audio
        video_bitrate = int((target_bits / duration) - audio_bitrate)

        if video_bitrate < 100000:  # Less than 100 kbps
            console.print("[bold red]Target size too small for this video duration.[/bold red]")
            console.print("[dim]Try a larger target size or shorter video.[/dim]")
            press_continue()
            return

        video_bitrate_k = video_bitrate // 1000
        console.print(f"[dim]Calculated video bitrate: {video_bitrate_k} kbps[/dim]")

        stream = ffmpeg.input(file_path)
        stream = ffmpeg.output(
            stream, final_output,
            **{
                'c:v': 'libx264',
                'b:v': f'{video_bitrate_k}k',
                'c:a': 'aac',
                'b:a': '128k',
                'preset': 'slow',
                'pass': 1,
                'f': 'null'
            }
        )

        # Two-pass encoding for better quality at target size
        console.print("[cyan]Pass 1 of 2...[/cyan]")
        first_pass = ffmpeg.input(file_path).output(
            '/dev/null' if os.name != 'nt' else 'NUL',
            **{
                'c:v': 'libx264',
                'b:v': f'{video_bitrate_k}k',
                'preset': 'slow',
                'pass': 1,
                'an': None,
                'f': 'null'
            }
        ).overwrite_output()

        if not run_command(first_pass, "Analyzing video (Pass 1)...", show_progress=True):
            console.print("[bold red]First pass failed.[/bold red]")
            press_continue()
            return

        console.print("[cyan]Pass 2 of 2...[/cyan]")
        second_pass = ffmpeg.input(file_path).output(
            final_output,
            **{
                'c:v': 'libx264',
                'b:v': f'{video_bitrate_k}k',
                'c:a': 'aac',
                'b:a': '128k',
                'preset': 'slow',
                'pass': 2
            }
        )

        if action_result == 'overwrite':
            second_pass = second_pass.overwrite_output()

        if run_command(second_pass, "Compressing video (Pass 2)...", show_progress=True):
            new_size = os.path.getsize(final_output) / (1024 * 1024)
            console.print(f"[bold green]Compressed: {file_size_mb:.1f} MB → {new_size:.1f} MB[/bold green]")
            console.print(f"[bold green]Saved to: {final_output}[/bold green]")
        else:
            console.print("[bold red]Compression failed.[/bold red]")

        # Cleanup pass log files
        for f in ['ffmpeg2pass-0.log', 'ffmpeg2pass-0.log.mbtree']:
            if os.path.exists(f):
                os.remove(f)

    else:  # Quality preset
        quality = questionary.select(
            "Select quality (lower CRF = higher quality, larger file):",
            choices=[
                "High quality (CRF 18) - Slight compression",
                "Medium quality (CRF 23) - Balanced",
                "Low quality (CRF 28) - Smaller file",
                "Very low quality (CRF 35) - Much smaller file"
            ]
        ).ask()

        if not quality:
            return

        crf_map = {
            "High": "18",
            "Medium": "23",
            "Low": "28",
            "Very": "35"
        }
        crf = crf_map.get(quality.split()[0], "23")

        if not check_disk_space(file_path):
            return

        stream = ffmpeg.input(file_path).output(
            final_output,
            **{
                'c:v': 'libx264',
                'crf': crf,
                'preset': 'medium',
                'c:a': 'aac',
                'b:a': '128k'
            }
        )

        if action_result == 'overwrite':
            stream = stream.overwrite_output()

        if run_command(stream, f"Compressing video (CRF {crf})...", show_progress=True):
            new_size = os.path.getsize(final_output) / (1024 * 1024)
            console.print(f"[bold green]Compressed: {file_size_mb:.1f} MB → {new_size:.1f} MB[/bold green]")
            console.print(f"[bold green]Saved to: {final_output}[/bold green]")
        else:
            console.print("[bold red]Compression failed.[/bold red]")

    press_continue()


def change_resolution(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        if video_stream:
            current_w = video_stream.get('width', '?')
            current_h = video_stream.get('height', '?')
            console.print(f"[dim]Current resolution: {current_w}x{current_h}[/dim]")
    except Exception:
        pass

    resolution = questionary.select(
        "Select target resolution:",
        choices=[
            "4K (3840x2160)",
            "1080p (1920x1080)",
            "720p (1280x720)",
            "480p (854x480)",
            "360p (640x360)",
            "Custom",
            "← Back"
        ]
    ).ask()

    if resolution == "← Back" or resolution is None:
        return

    if resolution == "Custom":
        width = questionary.text("Enter width (e.g., 1280):").ask()
        height = questionary.text("Enter height (e.g., 720, or -1 for auto):").ask()
        if not width or not height:
            return
        try:
            w = int(width)
            h = int(height)
        except ValueError:
            console.print("[bold red]Invalid dimensions.[/bold red]")
            press_continue()
            return
    else:
        res_map = {
            "4K": (3840, 2160),
            "1080p": (1920, 1080),
            "720p": (1280, 720),
            "480p": (854, 480),
            "360p": (640, 360)
        }
        key = resolution.split()[0]
        w, h = res_map.get(key, (1920, 1080))

    output_file = f"{Path(file_path).stem}_{h}p{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path)
    stream = stream.filter('scale', w=w, h=h)
    stream = ffmpeg.output(
        stream, final_output,
        **{'c:v': 'libx264', 'crf': 23, 'c:a': 'copy'}
    )

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Resizing to {w}x{h}...", show_progress=True):
        console.print(f"[bold green]Saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]Resolution change failed.[/bold red]")

    press_continue()
