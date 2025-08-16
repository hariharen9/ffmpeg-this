
import os
import logging
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.ui_utils import get_media_files

console = Console()


def batch_convert():
    """Convert all media files in the directory to a specific format."""
    media_files = get_media_files()
    if not media_files:
        console.print("[bold yellow]No media files found in the current directory.[/bold yellow]")
        questionary.press_any_key_to_continue().ask()
        return

    output_format = questionary.select(
        "Select output format for the batch conversion:",
        choices=["mp4", "mkv", "mov", "avi", "webm", "mp3", "flac", "wav", "gif"],
        use_indicator=True
    ).ask()
    if not output_format: return

    quality_preset = None
    if output_format in ["mp4", "mkv", "mov", "avi", "webm"]:
        quality_preset = questionary.select(
            "Select quality preset:",
            choices=["Same as source", "High (CRF 18)", "Medium (CRF 23)", "Low (CRF 28)"],
            use_indicator=True
        ).ask()
        if not quality_preset: return

    confirm = questionary.confirm(
        f"This will convert {len(media_files)} file(s) in the current directory to .{output_format}. Continue?",
        default=False
    ).ask()

    if not confirm:
        console.print("[bold yellow]Batch conversion cancelled.[/bold yellow]")
        return

    success_count = 0
    fail_count = 0

    for file in media_files:
        console.rule(f"Processing: {file}")
        file_path = os.path.abspath(file)
        is_gif = Path(file_path).suffix.lower() == '.gif'
        has_audio = has_audio_stream(file_path)

        if (is_gif or not has_audio) and output_format in ["mp3", "flac", "wav"]:
            console.print(f"[bold yellow]Skipping {file}: Source has no audio to convert.[/bold yellow]")
            continue

        output_file = f"{Path(file_path).stem}_batch.{output_format}"
        input_stream = ffmpeg.input(file_path)
        output_stream = None
        kwargs = {'y': None}

        try:
            if output_format in ["mp4", "mkv", "mov", "avi", "webm"]:
                if quality_preset == "Same as source":
                    kwargs['c'] = 'copy'
                else:
                    crf = quality_preset.split(" ")[-1][1:-1]
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
                kwargs['c:a'] = 'libmp3lame' if output_format == 'mp3' else output_format
                if output_format == 'mp3':
                    kwargs['b:a'] = '192k' # Default bitrate for batch
                output_stream = input_stream.output(output_file, **kwargs)

            elif output_format == "gif":
                fps = "15"
                scale = "480"
                palette_file = f"palette_{Path(file_path).stem}.png"
                
                palette_gen_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos').filter('palettegen')
                run_command(palette_gen_stream.output(palette_file, y=None), f"Generating palette for {file}...")

                if not os.path.exists(palette_file):
                    console.print(f"[bold red]Failed to generate color palette for {file}.[/bold red]")
                    fail_count += 1
                    continue

                palette_input = ffmpeg.input(palette_file)
                video_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos')
                final_stream = ffmpeg.filter([video_stream, palette_input], 'paletteuse')
                output_stream = final_stream.output(output_file, y=None)

            if output_stream and run_command(output_stream, f"Converting {file}...", show_progress=True):
                console.print(f"  -> [bold green]Successfully converted to {output_file}[/bold green]")
                success_count += 1
            else:
                console.print(f"  -> [bold red]Failed to convert {file}.[/bold red]")
                fail_count += 1

            if output_format == "gif" and os.path.exists(f"palette_{Path(file_path).stem}.png"):
                os.remove(f"palette_{Path(file_path).stem}.png")

        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred while processing {file}: {e}[/bold red]")
            logging.error(f"Batch convert error for file {file}: {e}")
            fail_count += 1

    console.rule("[bold green]Batch Conversion Complete[/bold green]")
    console.print(f"Successful: {success_count} | Failed: {fail_count}")
    questionary.press_any_key_to_continue().ask()
