import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, get_video_duration,
    format_duration, press_continue
)

console = Console()


def change_speed(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration > 0:
        console.print(f"[dim]Current duration: {format_duration(duration)}[/dim]")

    speed = questionary.select(
        "Select speed:",
        choices=[
            "0.25x (Very Slow)",
            "0.5x (Slow)",
            "0.75x (Slightly Slow)",
            "1.5x (Slightly Fast)",
            "2x (Fast)",
            "4x (Very Fast)",
            "Custom",
            "← Back"
        ]
    ).ask()

    if speed == "← Back" or speed is None:
        return

    if speed == "Custom":
        custom_speed = questionary.text(
            "Enter speed multiplier (e.g., 1.5 for 1.5x faster):",
            default="1.5"
        ).ask()
        if not custom_speed:
            return
        try:
            speed_factor = float(custom_speed)
            if speed_factor <= 0:
                console.print("[bold red]Speed must be positive.[/bold red]")
                press_continue()
                return
        except ValueError:
            console.print("[bold red]Invalid speed value.[/bold red]")
            press_continue()
            return
    else:
        speed_factor = float(speed.split('x')[0])

    new_duration = duration / speed_factor
    console.print(f"[dim]New duration will be: {format_duration(new_duration)}[/dim]")

    if speed_factor > 1:
        suffix = f"_{speed_factor}x_fast"
    else:
        suffix = f"_{speed_factor}x_slow"

    output_file = f"{Path(file_path).stem}{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # Video speed: setpts filter (lower = faster)
    video_tempo = 1 / speed_factor

    input_stream = ffmpeg.input(file_path)
    video = input_stream.video.filter('setpts', f'{video_tempo}*PTS')

    if has_audio_stream(file_path):
        # Audio speed: atempo filter (only supports 0.5 to 2.0)
        # Chain multiple atempo filters for larger changes
        audio = input_stream.audio

        if speed_factor > 2.0:
            # Chain atempo filters for speeds > 2x
            remaining = speed_factor
            while remaining > 2.0:
                audio = audio.filter('atempo', 2.0)
                remaining /= 2.0
            audio = audio.filter('atempo', remaining)
        elif speed_factor < 0.5:
            # Chain atempo filters for speeds < 0.5x
            remaining = speed_factor
            while remaining < 0.5:
                audio = audio.filter('atempo', 0.5)
                remaining /= 0.5
            audio = audio.filter('atempo', remaining)
        else:
            audio = audio.filter('atempo', speed_factor)

        stream = ffmpeg.output(video, audio, final_output, **{'c:v': 'libx264', 'crf': 23})
    else:
        stream = ffmpeg.output(video, final_output, **{'c:v': 'libx264', 'crf': 23})

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Changing speed to {speed_factor}x...", show_progress=True):
        console.print(f"[bold green]Saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]Speed change failed.[/bold red]")

    press_continue()


def reverse_video(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration > 60:
        console.print(f"[yellow]Warning: This is a {format_duration(duration)} video.[/yellow]")
        console.print("[dim]Reversing long videos requires loading into memory and may be slow.[/dim]")
        if not questionary.confirm("Continue?", default=False).ask():
            return

    output_file = f"{Path(file_path).stem}_reversed{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)
    video = input_stream.video.filter('reverse')

    if has_audio_stream(file_path):
        audio = input_stream.audio.filter('areverse')
        stream = ffmpeg.output(video, audio, final_output, **{'c:v': 'libx264', 'crf': 23})
    else:
        stream = ffmpeg.output(video, final_output, **{'c:v': 'libx264', 'crf': 23})

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Reversing video...", show_progress=True):
        console.print(f"[bold green]Saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]Reverse failed.[/bold red]")

    press_continue()
