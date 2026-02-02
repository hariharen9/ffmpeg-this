from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, check_has_video_stream, press_continue
)

console = Console()


def extract_audio(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    if not has_audio_stream(file_path):
        console.print("[bold red]Error: No audio stream found in the file.[/bold red]")
        press_continue()
        return

    audio_format = questionary.select(
        "Select audio format:",
        choices=["mp3", "flac", "wav"]
    ).ask()
    if not audio_format:
        return

    output_file = f"{Path(file_path).stem}_audio.{audio_format}"
    action_result, final_output = check_output_file(output_file, "Audio file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path).output(
        final_output,
        vn=None,
        acodec='libmp3lame' if audio_format == 'mp3' else audio_format
    )

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Extracting audio to {audio_format.upper()}...", show_progress=True):
        console.print(f"[bold green]Successfully extracted audio to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to extract audio.[/bold red]")

    press_continue()


def remove_audio(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found in the file.[/bold red]")
        press_continue()
        return

    output_file = f"{Path(file_path).stem}_no_audio{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path).output(final_output, vcodec='copy', an=None)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Removing audio track...", show_progress=True):
        console.print(f"[bold green]Successfully removed audio, saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to remove audio.[/bold red]")

    press_continue()
