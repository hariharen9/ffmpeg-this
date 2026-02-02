import os
import logging
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.ui_utils import get_media_files
from peg_this.utils.validation import check_disk_space, press_continue

console = Console()


def batch_convert():
    media_files = get_media_files()
    if not media_files:
        console.print("[bold yellow]No media files found in the current directory.[/bold yellow]")
        press_continue()
        return

    console.print(f"[dim]Found {len(media_files)} media file(s)[/dim]")

    output_format = questionary.select(
        "Select output format for the batch conversion:",
        choices=["mp4", "mkv", "mov", "avi", "webm", "mp3", "flac", "wav", "gif"]
    ).ask()
    if not output_format:
        return

    quality_preset = None
    if output_format in ["mp4", "mkv", "mov", "avi", "webm"]:
        quality_preset = questionary.select(
            "Select quality preset:",
            choices=["Same as source", "High (CRF 18)", "Medium (CRF 23)", "Low (CRF 28)"]
        ).ask()
        if not quality_preset:
            return

    # Estimate disk space needed
    total_size = sum(os.path.getsize(f) for f in media_files if os.path.exists(f))
    if total_size > 0 and not check_disk_space(media_files[0], multiplier=len(media_files)):
        return

    confirm = questionary.confirm(
        f"This will convert {len(media_files)} file(s) to .{output_format}. Continue?",
        default=False
    ).ask()

    if not confirm:
        console.print("[bold yellow]Batch conversion cancelled.[/bold yellow]")
        return

    success_count = 0
    fail_count = 0
    skipped_count = 0

    try:
        for i, file in enumerate(media_files):
            console.rule(f"[{i+1}/{len(media_files)}] Processing: {file}")
            file_path = os.path.abspath(file)

            if not os.path.exists(file_path):
                console.print(f"[yellow]Skipping {file}: File not found.[/yellow]")
                skipped_count += 1
                continue

            is_gif = Path(file_path).suffix.lower() == '.gif'
            has_audio = has_audio_stream(file_path)

            if (is_gif or not has_audio) and output_format in ["mp3", "flac", "wav"]:
                console.print(f"[yellow]Skipping {file}: Source has no audio to convert.[/yellow]")
                skipped_count += 1
                continue

            output_file = f"{Path(file_path).stem}_batch.{output_format}"

            # Skip if output already exists
            if os.path.exists(output_file):
                console.print(f"[yellow]Skipping {file}: Output already exists ({output_file})[/yellow]")
                skipped_count += 1
                continue

            input_stream = ffmpeg.input(file_path)
            output_stream = None
            kwargs = {}

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
                        kwargs['b:a'] = '192k'
                    output_stream = input_stream.output(output_file, **kwargs)

                elif output_format == "gif":
                    fps = 15
                    scale = 480
                    palette_file = f"palette_{Path(file_path).stem}.png"

                    try:
                        palette_gen_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos').filter('palettegen')
                        run_command(palette_gen_stream.output(palette_file).overwrite_output(), f"Generating palette for {file}...")

                        if not os.path.exists(palette_file):
                            console.print(f"[red]Failed to generate color palette for {file}.[/red]")
                            fail_count += 1
                            continue

                        palette_input = ffmpeg.input(palette_file)
                        video_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos')
                        final_stream = ffmpeg.filter([video_stream, palette_input], 'paletteuse')
                        output_stream = final_stream.output(output_file)
                    finally:
                        if os.path.exists(palette_file):
                            os.remove(palette_file)

                if output_stream and run_command(output_stream, f"Converting {file}...", show_progress=True):
                    console.print(f"  -> [green]Successfully converted to {output_file}[/green]")
                    success_count += 1
                else:
                    console.print(f"  -> [red]Failed to convert {file}.[/red]")
                    fail_count += 1

            except Exception as e:
                console.print(f"[red]Error processing {file}: {e}[/red]")
                logging.error(f"Batch convert error for file {file}: {e}")
                fail_count += 1

    except KeyboardInterrupt:
        console.print("\n[yellow]Batch conversion interrupted by user.[/yellow]")

    console.rule("[bold green]Batch Conversion Complete[/bold green]")
    console.print(f"Successful: {success_count} | Failed: {fail_count} | Skipped: {skipped_count}")
    press_continue()
