
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream

console = Console()


def trim_video(file_path):
    """Cut a video by specifying start and end times."""
    start_time = questionary.text("Enter start time (HH:MM:SS or seconds):").ask()
    if not start_time: return
    end_time = questionary.text("Enter end time (HH:MM:SS or seconds):").ask()
    if not end_time: return

    output_file = f"{Path(file_path).stem}_trimmed{Path(file_path).suffix}"
    
    input_stream = ffmpeg.input(file_path)
    
    # Build output with accurate seeking
    output_kwargs = {
        'ss': start_time,
        'to': end_time,
        'y': None
    }
    
    # Handle audio stream if present
    if has_audio_stream(file_path):
        output_kwargs['c:a'] = 'copy'  # Audio can still be copied
        stream = ffmpeg.output(input_stream.video, input_stream.audio, output_file, **output_kwargs)
    else:
        stream = ffmpeg.output(input_stream, output_file, **output_kwargs)
    
    run_command(stream, "Trimming video...", show_progress=True)
    console.print(f"[bold green]Successfully trimmed to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()
