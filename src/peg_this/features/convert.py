
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


def convert_image(file_path):
    """Convert an image to a different format."""
    output_format = questionary.select(
        "Select the output format:",
        choices=["jpg", "png", "webp", "bmp", "tiff"],
        use_indicator=True
    ).ask()
    if not output_format: return

    output_file = f"{Path(file_path).stem}_converted.{output_format}"
    kwargs = {'y': None}
    
    # For JPG and WEBP, allow quality selection
    if output_format in ['jpg', 'webp']:
        quality_preset = questionary.select(
            "Select quality preset:",
            choices=["High (95%)", "Medium (80%)", "Low (60%)"],
            use_indicator=True
        ).ask()
        if not quality_preset: return

        quality_map = {"High (95%)": "95", "Medium (80%)": "80", "Low (60%)": "60"}
        quality = quality_map[quality_preset]

        if output_format == 'jpg':
            q_scale = int(31 - (int(quality) / 100.0) * 30)
            kwargs['q:v'] = q_scale
        elif output_format == 'webp':
            kwargs['quality'] = quality

    stream = ffmpeg.input(file_path).output(output_file, **kwargs)
    
    if run_command(stream, f"Converting to {output_format.upper()}..."):
        console.print(f"[bold green]Successfully converted image to {output_file}[/bold green]")
    else:
        console.print("[bold red]Image conversion failed.[/bold red]")
    
    questionary.press_any_key_to_continue().ask()


def resize_image(file_path):
    """Resize an image to new dimensions."""
    console.print("Enter new dimensions. Use [bold]-1[/bold] for one dimension to preserve aspect ratio.")
    width = questionary.text("Enter new width (e.g., 1280 or -1):").ask()
    if not width: return
    height = questionary.text("Enter new height (e.g., 720 or -1):").ask()
    if not height: return

    try:
        if int(width) == -1 and int(height) == -1:
            console.print("[bold red]Error: Width and Height cannot both be -1.[/bold red]")
            questionary.press_any_key_to_continue().ask()
            return
    except ValueError:
        console.print("[bold red]Error: Invalid dimensions. Please enter numbers.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return

    output_file = f"{Path(file_path).stem}_resized{Path(file_path).suffix}"
    
    stream = ffmpeg.input(file_path).filter('scale', w=width, h=height).output(output_file, y=None)
    
    if run_command(stream, "Resizing image..."):
        console.print(f"[bold green]Successfully resized image to {output_file}[/bold green]")
    else:
        console.print("[bold red]Image resizing failed.[/bold red]")
        
    questionary.press_any_key_to_continue().ask()


def rotate_image(file_path):
    """Rotate an image."""
    rotation = questionary.select(
        "Select rotation:",
        choices=[
            "90 degrees clockwise",
            "90 degrees counter-clockwise",
            "180 degrees"
        ],
        use_indicator=True
    ).ask()
    if not rotation: return

    output_file = f"{Path(file_path).stem}_rotated{Path(file_path).suffix}"
    
    stream = ffmpeg.input(file_path)
    if rotation == "90 degrees clockwise":
        stream = stream.filter('transpose', 1)
    elif rotation == "90 degrees counter-clockwise":
        stream = stream.filter('transpose', 2)
    elif rotation == "180 degrees":
        # Apply 90-degree rotation twice for 180 degrees
        stream = stream.filter('transpose', 2).filter('transpose', 2)

    output_stream = stream.output(output_file, y=None)
    
    if run_command(output_stream, "Rotating image..."):
        console.print(f"[bold green]Successfully rotated image and saved to {output_file}[/bold green]")
    else:
        console.print("[bold red]Image rotation failed.[/bold red]")
        
    questionary.press_any_key_to_continue().ask()


def flip_image(file_path):
    """Flip an image horizontally or vertically."""
    flip_direction = questionary.select(
        "Select flip direction:",
        choices=["Horizontal", "Vertical"],
        use_indicator=True
    ).ask()
    if not flip_direction: return

    output_file = f"{Path(file_path).stem}_flipped{Path(file_path).suffix}"
    
    stream = ffmpeg.input(file_path)
    if flip_direction == "Horizontal":
        stream = stream.filter('hflip')
    else:
        stream = stream.filter('vflip')

    output_stream = stream.output(output_file, y=None)
    
    if run_command(output_stream, "Flipping image..."):
        console.print(f"[bold green]Successfully flipped image and saved to {output_file}[/bold green]")
    else:
        console.print("[bold red]Image flipping failed.[/bold red]")
        
    questionary.press_any_key_to_continue().ask()

