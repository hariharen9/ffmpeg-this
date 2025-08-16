
import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream

console = Console()


def convert_file(file_path):
    """Convert the file to a different format."""
    is_gif = Path(file_path).suffix.lower() == '.gif'
    has_audio = has_audio_stream(file_path)

    output_format = questionary.select("Select the output format:", choices=["mp4", "mkv", "mov", "avi", "webm", "mp3", "flac", "wav", "gif"], use_indicator=True).ask()
    if not output_format: return

    if (is_gif or not has_audio) and output_format in ["mp3", "flac", "wav"]:
        console.print("[bold red]Error: Source has no audio to convert.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return

    output_file = f"{Path(file_path).stem}_converted.{output_format}"
    
    input_stream = ffmpeg.input(file_path)
    output_stream = None
    kwargs = {'y': None}

    if output_format in ["mp4", "mkv", "mov", "avi", "webm"]:
        quality = questionary.select("Select quality preset:", choices=["Same as source", "High (CRF 18)", "Medium (CRF 23)", "Low (CRF 28)"], use_indicator=True).ask()
        if not quality: return

        if quality == "Same as source":
            kwargs['c'] = 'copy'
        else:
            crf = quality.split(" ")[-1][1:-1]
            kwargs['c:v'] = 'libx264'
            kwargs['crf'] = crf
            kwargs['pix_fmt'] = 'yuv420p'
            if has_audio:
                kwargs['c:a'] = 'aac'
                kwargs['b:a'] = '192k'
            else:
                kwargs['an'] = None
        output_stream = input_stream.output(output_file, **kwargs)

    elif output_format in ["mp3", "flac", "wav"]:
        kwargs['vn'] = None
        if output_format == 'mp3':
            bitrate = questionary.select("Select audio bitrate:", choices=["128k", "192k", "256k", "320k"]).ask()
            if not bitrate: return
            kwargs['c:a'] = 'libmp3lame'
            kwargs['b:a'] = bitrate
        else:
            kwargs['c:a'] = output_format
        output_stream = input_stream.output(output_file, **kwargs)

    elif output_format == "gif":
        fps = questionary.text("Enter frame rate (e.g., 15):", default="15").ask()
        if not fps: return
        scale = questionary.text("Enter width in pixels (e.g., 480):", default="480").ask()
        if not scale: return
        
        palette_file = f"palette_{Path(file_path).stem}.png"
        
        # Correctly chain filters for palette generation using explicit w/h arguments
        palette_gen_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos').filter('palettegen')
        run_command(palette_gen_stream.output(palette_file, y=None), "Generating color palette...")

        if not os.path.exists(palette_file):
            console.print("[bold red]Failed to generate color palette for GIF.[/bold red]")
            questionary.press_any_key_to_continue().ask()
            return

        palette_input = ffmpeg.input(palette_file)
        video_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos')
        
        final_stream = ffmpeg.filter([video_stream, palette_input], 'paletteuse')
        output_stream = final_stream.output(output_file, y=None)

    if output_stream and run_command(output_stream, f"Converting to {output_format}...", show_progress=True):
        console.print(f"[bold green]Successfully converted to {output_file}[/bold green]")
    else:
        console.print("[bold red]Conversion failed.[/bold red]")

    if output_format == "gif" and os.path.exists(f"palette_{Path(file_path).stem}.png"):
        os.remove(f"palette_{Path(file_path).stem}.png")
        
    questionary.press_any_key_to_continue().ask()
