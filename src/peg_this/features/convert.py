import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, validate_positive_integer, press_continue
)

console = Console()


def convert_file(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    is_gif = Path(file_path).suffix.lower() == '.gif'
    has_audio = has_audio_stream(file_path)

    output_format = questionary.select(
        "Select the output format:",
        choices=["mp4", "mkv", "mov", "avi", "webm", "mp3", "flac", "wav", "gif"]
    ).ask()
    if not output_format:
        return

    if (is_gif or not has_audio) and output_format in ["mp3", "flac", "wav"]:
        console.print("[bold red]Error: Source has no audio to convert.[/bold red]")
        press_continue()
        return

    output_file = f"{Path(file_path).stem}_converted.{output_format}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)
    output_stream = None
    kwargs = {}

    if output_format in ["mp4", "mkv", "mov", "avi", "webm"]:
        quality = questionary.select(
            "Select quality preset:",
            choices=["Same as source", "High (CRF 18)", "Medium (CRF 23)", "Low (CRF 28)"]
        ).ask()
        if not quality:
            return

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
        output_stream = input_stream.output(final_output, **kwargs)

    elif output_format in ["mp3", "flac", "wav"]:
        kwargs['vn'] = None
        if output_format == 'mp3':
            bitrate = questionary.select(
                "Select audio bitrate:",
                choices=["128k", "192k", "256k", "320k"]
            ).ask()
            if not bitrate:
                return
            kwargs['c:a'] = 'libmp3lame'
            kwargs['b:a'] = bitrate
        else:
            kwargs['c:a'] = output_format
        output_stream = input_stream.output(final_output, **kwargs)

    elif output_format == "gif":
        fps = questionary.text("Enter frame rate (e.g., 15):", default="15").ask()
        if not fps:
            return
        fps_val = validate_positive_integer(fps, "Frame rate")
        if not fps_val:
            press_continue()
            return

        scale = questionary.text("Enter width in pixels (e.g., 480):", default="480").ask()
        if not scale:
            return
        scale_val = validate_positive_integer(scale, "Width")
        if not scale_val:
            press_continue()
            return

        palette_file = f"palette_{Path(file_path).stem}.png"

        try:
            palette_gen_stream = input_stream.video.filter('fps', fps=fps_val).filter('scale', w=scale_val, h=-1, flags='lanczos').filter('palettegen')
            run_command(palette_gen_stream.output(palette_file).overwrite_output(), "Generating color palette...")

            if not os.path.exists(palette_file):
                console.print("[bold red]Failed to generate color palette for GIF.[/bold red]")
                press_continue()
                return

            palette_input = ffmpeg.input(palette_file)
            video_stream = input_stream.video.filter('fps', fps=fps_val).filter('scale', w=scale_val, h=-1, flags='lanczos')
            final_stream = ffmpeg.filter([video_stream, palette_input], 'paletteuse')
            output_stream = final_stream.output(final_output)

        finally:
            if os.path.exists(palette_file):
                os.remove(palette_file)

    if output_stream:
        if action_result == 'overwrite':
            output_stream = output_stream.overwrite_output()

        if run_command(output_stream, f"Converting to {output_format}...", show_progress=True):
            console.print(f"[bold green]Successfully converted to {final_output}[/bold green]")
        else:
            console.print("[bold red]Conversion failed.[/bold red]")

    press_continue()


def convert_image(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    output_format = questionary.select(
        "Select the output format:",
        choices=["jpg", "png", "webp", "bmp", "tiff"]
    ).ask()
    if not output_format:
        return

    output_file = f"{Path(file_path).stem}_converted.{output_format}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    kwargs = {}

    if output_format in ['jpg', 'webp']:
        quality_preset = questionary.select(
            "Select quality preset:",
            choices=["High (95%)", "Medium (80%)", "Low (60%)"]
        ).ask()
        if not quality_preset:
            return

        quality_map = {"High (95%)": "95", "Medium (80%)": "80", "Low (60%)": "60"}
        quality = quality_map[quality_preset]

        if output_format == 'jpg':
            q_scale = int(31 - (int(quality) / 100.0) * 30)
            kwargs['q:v'] = q_scale
        elif output_format == 'webp':
            kwargs['quality'] = quality

    stream = ffmpeg.input(file_path).output(final_output, **kwargs)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Converting to {output_format.upper()}..."):
        console.print(f"[bold green]Successfully converted image to {final_output}[/bold green]")
    else:
        console.print("[bold red]Image conversion failed.[/bold red]")

    press_continue()


def resize_image(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    console.print("Enter new dimensions. Use [bold]-1[/bold] for one dimension to preserve aspect ratio.")
    width = questionary.text("Enter new width (e.g., 1280 or -1):").ask()
    if not width:
        return
    height = questionary.text("Enter new height (e.g., 720 or -1):").ask()
    if not height:
        return

    width_val = validate_positive_integer(width, "Width")
    height_val = validate_positive_integer(height, "Height")

    if width_val is None or height_val is None:
        press_continue()
        return

    if width_val == -1 and height_val == -1:
        console.print("[bold red]Error: Width and Height cannot both be -1.[/bold red]")
        press_continue()
        return

    output_file = f"{Path(file_path).stem}_resized{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path).filter('scale', w=width_val, h=height_val).output(final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Resizing image..."):
        console.print(f"[bold green]Successfully resized image to {final_output}[/bold green]")
    else:
        console.print("[bold red]Image resizing failed.[/bold red]")

    press_continue()


def rotate_image(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    rotation = questionary.select(
        "Select rotation:",
        choices=["90 degrees clockwise", "90 degrees counter-clockwise", "180 degrees"]
    ).ask()
    if not rotation:
        return

    output_file = f"{Path(file_path).stem}_rotated{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path)
    if rotation == "90 degrees clockwise":
        stream = stream.filter('transpose', 1)
    elif rotation == "90 degrees counter-clockwise":
        stream = stream.filter('transpose', 2)
    elif rotation == "180 degrees":
        stream = stream.filter('transpose', 2).filter('transpose', 2)

    output_stream = stream.output(final_output)

    if action_result == 'overwrite':
        output_stream = output_stream.overwrite_output()

    if run_command(output_stream, "Rotating image..."):
        console.print(f"[bold green]Successfully rotated image and saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Image rotation failed.[/bold red]")

    press_continue()


def flip_image(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    flip_direction = questionary.select(
        "Select flip direction:",
        choices=["Horizontal", "Vertical"]
    ).ask()
    if not flip_direction:
        return

    output_file = f"{Path(file_path).stem}_flipped{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path)
    if flip_direction == "Horizontal":
        stream = stream.filter('hflip')
    else:
        stream = stream.filter('vflip')

    output_stream = stream.output(final_output)

    if action_result == 'overwrite':
        output_stream = output_stream.overwrite_output()

    if run_command(output_stream, "Flipping image..."):
        console.print(f"[bold green]Successfully flipped image and saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Image flipping failed.[/bold red]")

    press_continue()
