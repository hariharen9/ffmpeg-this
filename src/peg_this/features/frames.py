import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command
from peg_this.utils.validation import (
    validate_input_file, check_output_file, check_disk_space,
    get_video_duration, format_duration, press_continue
)

console = Console()


def extract_frames(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration > 0:
        console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

    mode = questionary.select(
        "How would you like to extract frames?",
        choices=[
            "Single frame at timestamp",
            "Every N seconds",
            "Every N frames",
            "All frames (warning: many files)",
            "← Back"
        ]
    ).ask()

    if mode == "← Back" or mode is None:
        return

    output_dir = f"{Path(file_path).stem}_frames"

    if mode == "Single frame at timestamp":
        timestamp = questionary.text(
            "Enter timestamp (e.g., 00:01:30 or 90):",
            default="0"
        ).ask()
        if not timestamp:
            return

        output_file = f"{Path(file_path).stem}_frame.png"
        action_result, final_output = check_output_file(output_file, "Image file")

        if action_result == 'cancel':
            return

        stream = ffmpeg.input(file_path, ss=timestamp).output(
            final_output, vframes=1, **{'q:v': 2}
        )

        if action_result == 'overwrite':
            stream = stream.overwrite_output()

        if run_command(stream, "Extracting frame..."):
            console.print(f"[bold green]Saved to: {final_output}[/bold green]")
        else:
            console.print("[bold red]Frame extraction failed.[/bold red]")

    else:
        if os.path.exists(output_dir):
            console.print(f"[yellow]Directory '{output_dir}' already exists.[/yellow]")
            if not questionary.confirm("Continue and add frames there?", default=True).ask():
                return
        else:
            os.makedirs(output_dir)
            console.print(f"[dim]Created directory: {output_dir}[/dim]")

        if mode == "Every N seconds":
            interval = questionary.text("Extract a frame every N seconds:", default="1").ask()
            if not interval:
                return
            try:
                fps_value = 1 / float(interval)
            except (ValueError, ZeroDivisionError):
                console.print("[bold red]Invalid interval.[/bold red]")
                press_continue()
                return

            output_pattern = os.path.join(output_dir, "frame_%04d.png")
            stream = ffmpeg.input(file_path).filter('fps', fps=fps_value).output(
                output_pattern, **{'q:v': 2}
            ).overwrite_output()

        elif mode == "Every N frames":
            n_frames = questionary.text("Extract every Nth frame:", default="30").ask()
            if not n_frames:
                return
            try:
                n = int(n_frames)
            except ValueError:
                console.print("[bold red]Invalid number.[/bold red]")
                press_continue()
                return

            output_pattern = os.path.join(output_dir, "frame_%04d.png")
            stream = ffmpeg.input(file_path).filter('select', f'not(mod(n,{n}))').output(
                output_pattern, vsync='vfr', **{'q:v': 2}
            ).overwrite_output()

        else:  # All frames
            try:
                probe = ffmpeg.probe(file_path)
                video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
                if video_stream:
                    fps = eval(video_stream.get('r_frame_rate', '30/1'))
                    estimated_frames = int(duration * fps)
                    console.print(f"[yellow]This will extract approximately {estimated_frames} frames.[/yellow]")
                    console.print(f"[dim]Estimated disk space: ~{estimated_frames * 0.5:.0f} MB[/dim]")
                    if not questionary.confirm("Continue?", default=False).ask():
                        return
            except Exception:
                pass

            output_pattern = os.path.join(output_dir, "frame_%06d.png")
            stream = ffmpeg.input(file_path).output(
                output_pattern, **{'q:v': 2}
            ).overwrite_output()

        if run_command(stream, "Extracting frames...", show_progress=True):
            frame_count = len([f for f in os.listdir(output_dir) if f.endswith('.png')])
            console.print(f"[bold green]Extracted {frame_count} frames to: {output_dir}/[/bold green]")
        else:
            console.print("[bold red]Frame extraction failed.[/bold red]")

    press_continue()


def split_video(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration <= 0:
        console.print("[bold red]Could not determine video duration.[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

    method = questionary.select(
        "How would you like to split?",
        choices=[
            "Into equal parts",
            "By duration (e.g., 30 seconds each)",
            "← Back"
        ]
    ).ask()

    if method == "← Back" or method is None:
        return

    if method == "Into equal parts":
        num_parts = questionary.text("How many parts?", default="2").ask()
        if not num_parts:
            return
        try:
            parts = int(num_parts)
            if parts < 2:
                console.print("[bold red]Must be at least 2 parts.[/bold red]")
                press_continue()
                return
        except ValueError:
            console.print("[bold red]Invalid number.[/bold red]")
            press_continue()
            return

        segment_duration = duration / parts

    else:  # By duration
        seg_duration = questionary.text("Duration per segment (in seconds):", default="30").ask()
        if not seg_duration:
            return
        try:
            segment_duration = float(seg_duration)
            if segment_duration <= 0:
                console.print("[bold red]Duration must be positive.[/bold red]")
                press_continue()
                return
        except ValueError:
            console.print("[bold red]Invalid duration.[/bold red]")
            press_continue()
            return

        parts = int(duration / segment_duration) + 1

    console.print(f"[dim]Will create {parts} segments of ~{format_duration(segment_duration)} each[/dim]")

    if not check_disk_space(file_path, multiplier=1.5):
        return

    output_pattern = f"{Path(file_path).stem}_part%03d{Path(file_path).suffix}"

    stream = ffmpeg.input(file_path).output(
        output_pattern,
        **{
            'c': 'copy',
            'f': 'segment',
            'segment_time': segment_duration,
            'reset_timestamps': 1
        }
    ).overwrite_output()

    if run_command(stream, "Splitting video...", show_progress=True):
        console.print(f"[bold green]Split into {parts} parts: {Path(file_path).stem}_part001, etc.[/bold green]")
    else:
        console.print("[bold red]Split failed.[/bold red]")

    press_continue()
