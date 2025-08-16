
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream

console = Console()


def extract_audio(file_path):
    """Extract the audio track from a video file."""
    if not has_audio_stream(file_path):
        console.print("[bold red]Error: No audio stream found in the file.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return

    audio_format = questionary.select("Select audio format:", choices=["mp3", "flac", "wav"], use_indicator=True).ask()
    if not audio_format: return

    output_file = f"{Path(file_path).stem}_audio.{audio_format}"
    stream = ffmpeg.input(file_path).output(output_file, vn=None, acodec='libmp3lame' if audio_format == 'mp3' else audio_format, y=None)
    
    run_command(stream, f"Extracting audio to {audio_format.upper()}...", show_progress=True)
    console.print(f"[bold green]Successfully extracted audio to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()


def remove_audio(file_path):
    """Create a silent version of a video."""
    output_file = f"{Path(file_path).stem}_no_audio{Path(file_path).suffix}"
    stream = ffmpeg.input(file_path).output(output_file, vcodec='copy', an=None, y=None)
    
    run_command(stream, "Removing audio track...", show_progress=True)
    console.print(f"[bold green]Successfully removed audio, saved to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()
