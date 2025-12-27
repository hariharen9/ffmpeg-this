from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, get_video_duration,
    validate_time_range, format_duration, warn_reencode, press_continue
)

console = Console()


def trim_video(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration > 0:
        console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

    start_time = questionary.text("Enter start time (HH:MM:SS or seconds):").ask()
    if not start_time:
        return

    end_time = questionary.text("Enter end time (HH:MM:SS or seconds):").ask()
    if not end_time:
        return

    start_secs, end_secs = validate_time_range(start_time, end_time, duration if duration > 0 else None)
    if start_secs is None:
        press_continue()
        return

    output_file = f"{Path(file_path).stem}_trimmed{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    warn_reencode("Trimming with accurate start time")

    input_stream = ffmpeg.input(file_path)

    if has_audio_stream(file_path):
        stream = ffmpeg.output(
            input_stream.video, input_stream.audio, final_output,
            ss=start_secs, to=end_secs, **{'c:v': 'libx264', 'crf': 23, 'c:a': 'copy'}
        )
    else:
        stream = ffmpeg.output(
            input_stream, final_output,
            ss=start_secs, to=end_secs, **{'c:v': 'libx264', 'crf': 23}
        )

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Trimming video...", show_progress=True):
        console.print(f"[bold green]Successfully trimmed to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to trim video.[/bold red]")

    press_continue()
