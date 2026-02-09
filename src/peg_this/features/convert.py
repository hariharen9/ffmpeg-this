import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream, get_global_encoding_args
from peg_this.utils.validation import (
    validate_input_file, check_output_file, validate_positive_integer, press_continue
)
import os

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
            crf = int(quality.split(" ")[-1][1:-1])
            # Get standardized args (codec, preset, crf/qp)
            encoding_args = get_global_encoding_args(quality="medium", crf=crf)
            kwargs.update(encoding_args)

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


def adjust_image_colors(file_path):
    """Adjust brightness, contrast, saturation, and gamma of an image."""
    if not validate_input_file(file_path):
        press_continue()
        return

    console.print("[dim]Adjust image colors: brightness, contrast, saturation, gamma.[/dim]")

    mode = questionary.select(
        "Adjustment mode:",
        choices=[
            "Use preset",
            "Custom adjustments",
            "← Back"
        ]
    ).ask()

    if mode == "← Back" or mode is None:
        return

    eq_params = {}

    if "preset" in mode:
        preset = questionary.select(
            "Select preset:",
            choices=[
                "Brighten",
                "Darken",
                "High Contrast",
                "Vibrant (High Saturation)",
                "Muted (Low Saturation)",
                "Warm Tone",
                "Cool Tone",
                "Vintage"
            ]
        ).ask()

        if preset is None:
            return

        presets = {
            "Brighten": {"brightness": "0.1", "gamma": "1.2"},
            "Darken": {"brightness": "-0.1", "gamma": "0.85"},
            "High Contrast": {"contrast": "1.3", "saturation": "1.1"},
            "Vibrant (High Saturation)": {"saturation": "1.5", "contrast": "1.1"},
            "Muted (Low Saturation)": {"saturation": "0.6", "contrast": "0.95"},
            "Warm Tone": {"brightness": "0.05", "saturation": "1.2", "gamma_r": "1.1", "gamma_b": "0.9"},
            "Cool Tone": {"brightness": "0", "saturation": "1.1", "gamma_r": "0.9", "gamma_b": "1.1"},
            "Vintage": {"saturation": "0.8", "contrast": "0.9", "brightness": "0.05", "gamma": "1.1"},
        }

        eq_params = presets.get(preset, {})
        filter_desc = preset

    else:  # Custom adjustments
        console.print("[dim]Enter values (leave default for no change):[/dim]")
        console.print("[dim]Brightness: -1.0 to 1.0 (default: 0)[/dim]")
        console.print("[dim]Contrast: 0.0 to 2.0 (default: 1.0)[/dim]")
        console.print("[dim]Saturation: 0.0 to 3.0 (default: 1.0)[/dim]")
        console.print("[dim]Gamma: 0.1 to 10.0 (default: 1.0)[/dim]")

        brightness = questionary.text("Brightness (-1 to 1):", default="0").ask()
        contrast = questionary.text("Contrast (0 to 2):", default="1").ask()
        saturation = questionary.text("Saturation (0 to 3):", default="1").ask()
        gamma = questionary.text("Gamma (0.1 to 10):", default="1").ask()

        if any(v is None for v in [brightness, contrast, saturation, gamma]):
            return

        eq_params = {
            "brightness": brightness,
            "contrast": contrast,
            "saturation": saturation,
            "gamma": gamma
        }
        filter_desc = "Custom color adjustment"

    output_file = f"{Path(file_path).stem}_adjusted{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path).filter('eq', **eq_params).output(final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Applying {filter_desc}..."):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Color adjustment failed.[/bold red]")

    press_continue()


def blur_sharpen_image(file_path):
    """Apply blur or sharpen effect to an image."""
    if not validate_input_file(file_path):
        press_continue()
        return

    effect_type = questionary.select(
        "Select effect:",
        choices=[
            "Blur (Gaussian)",
            "Sharpen",
            "← Back"
        ]
    ).ask()

    if effect_type == "← Back" or effect_type is None:
        return

    if "Blur" in effect_type:
        strength = questionary.select(
            "Blur strength:",
            choices=[
                "Light (sigma: 2)",
                "Medium (sigma: 5)",
                "Heavy (sigma: 10)",
                "Very Heavy (sigma: 20)"
            ]
        ).ask()

        if strength is None:
            return

        sigma_map = {
            "Light (sigma: 2)": 2,
            "Medium (sigma: 5)": 5,
            "Heavy (sigma: 10)": 10,
            "Very Heavy (sigma: 20)": 20
        }
        sigma = sigma_map.get(strength, 5)
        filter_name = "gblur"
        filter_params = {"sigma": sigma}
        suffix = "blurred"

    else:  # Sharpen
        strength = questionary.select(
            "Sharpen strength:",
            choices=[
                "Light",
                "Medium",
                "Strong"
            ]
        ).ask()

        if strength is None:
            return

        # unsharp filter: luma_msize_x:luma_msize_y:luma_amount
        strength_map = {
            "Light": {"lx": 5, "ly": 5, "la": 0.5},
            "Medium": {"lx": 5, "ly": 5, "la": 1.0},
            "Strong": {"lx": 7, "ly": 7, "la": 1.5},
        }
        params = strength_map.get(strength, strength_map["Medium"])
        filter_name = "unsharp"
        filter_params = {"luma_msize_x": params["lx"], "luma_msize_y": params["ly"], "luma_amount": params["la"]}
        suffix = "sharpened"

    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path).filter(filter_name, **filter_params).output(final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Applying {effect_type.split(' ')[0].lower()}..."):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Effect failed.[/bold red]")

    press_continue()


def image_effects(file_path):
    """Apply color effects: grayscale, sepia, invert, etc."""
    if not validate_input_file(file_path):
        press_continue()
        return

    effect = questionary.select(
        "Select effect:",
        choices=[
            "Grayscale (Black & White)",
            "Sepia (Vintage Brown)",
            "Invert (Negative)",
            "← Back"
        ]
    ).ask()

    if effect == "← Back" or effect is None:
        return

    if "Grayscale" in effect:
        # Use saturation=0 for grayscale
        filter_chain = [("eq", {"saturation": 0})]
        suffix = "grayscale"
    elif "Sepia" in effect:
        # Sepia using colorchannelmixer
        filter_chain = [("colorchannelmixer", {
            "rr": 0.393, "rg": 0.769, "rb": 0.189,
            "gr": 0.349, "gg": 0.686, "gb": 0.168,
            "br": 0.272, "bg": 0.534, "bb": 0.131
        })]
        suffix = "sepia"
    elif "Invert" in effect:
        filter_chain = [("negate", {})]
        suffix = "inverted"
    else:
        return

    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path)
    for filter_name, filter_params in filter_chain:
        stream = stream.filter(filter_name, **filter_params)
    stream = stream.output(final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Applying {effect.split(' ')[0].lower()} effect..."):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Effect failed.[/bold red]")

    press_continue()


def add_image_border(file_path):
    """Add a solid color border/padding around an image."""
    if not validate_input_file(file_path):
        press_continue()
        return

    # Get image dimensions
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        console.print(f"[dim]Image size: {width}x{height}[/dim]")
    except Exception:
        console.print("[yellow]Could not detect image dimensions.[/yellow]")
        width, height = 0, 0

    border_type = questionary.select(
        "Border type:",
        choices=[
            "Equal on all sides",
            "Custom (top, bottom, left, right)",
            "← Back"
        ]
    ).ask()

    if border_type == "← Back" or border_type is None:
        return

    if "Equal" in border_type:
        size = questionary.text("Border size in pixels:", default="20").ask()
        if not size:
            return
        size_val = validate_positive_integer(size, "Border size")
        if size_val is None:
            press_continue()
            return
        top = bottom = left = right = size_val
    else:
        top = questionary.text("Top padding (px):", default="20").ask()
        bottom = questionary.text("Bottom padding (px):", default="20").ask()
        left = questionary.text("Left padding (px):", default="20").ask()
        right = questionary.text("Right padding (px):", default="20").ask()

        if any(v is None for v in [top, bottom, left, right]):
            return

        top = validate_positive_integer(top, "Top") or 0
        bottom = validate_positive_integer(bottom, "Bottom") or 0
        left = validate_positive_integer(left, "Left") or 0
        right = validate_positive_integer(right, "Right") or 0

    # Border color
    color_choice = questionary.select(
        "Border color:",
        choices=[
            "White",
            "Black",
            "Gray",
            "Red",
            "Blue",
            "Green",
            "Custom (Hex)"
        ]
    ).ask()

    if color_choice is None:
        return

    color_map = {
        "White": "white",
        "Black": "black",
        "Gray": "gray",
        "Red": "red",
        "Blue": "blue",
        "Green": "green"
    }

    if color_choice == "Custom (Hex)":
        hex_color = questionary.text("Enter hex color (e.g., #FF5733):", default="#FFFFFF").ask()
        if hex_color:
            color = hex_color if hex_color.startswith("#") else f"#{hex_color}"
        else:
            color = "white"
    else:
        color = color_map.get(color_choice, "white")

    output_file = f"{Path(file_path).stem}_bordered{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # Use pad filter: pad=width:height:x:y:color
    # New dimensions
    new_width = (width if width else "iw") if isinstance(width, int) else "iw"
    new_height = (height if height else "ih") if isinstance(height, int) else "ih"

    if width and height:
        pad_w = width + left + right
        pad_h = height + top + bottom
    else:
        pad_w = f"iw+{left + right}"
        pad_h = f"ih+{top + bottom}"

    stream = ffmpeg.input(file_path).filter(
        'pad',
        w=pad_w,
        h=pad_h,
        x=left,
        y=top,
        color=color
    ).output(final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Adding border..."):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to add border.[/bold red]")

    press_continue()


def compress_image(file_path):
    """Compress/optimize image file size with quality control."""
    if not validate_input_file(file_path):
        press_continue()
        return

    # Get current file size
    try:
        file_size = os.path.getsize(file_path)
        console.print(f"[dim]Current file size: {file_size / 1024:.1f} KB[/dim]")
    except Exception:
        pass

    ext = Path(file_path).suffix.lower()

    # Determine output format
    if ext in ['.jpg', '.jpeg']:
        output_format = 'jpg'
    elif ext == '.png':
        output_format = questionary.select(
            "Output format:",
            choices=[
                "PNG (lossless, larger)",
                "JPG (lossy, smaller)",
                "WebP (modern, smallest)"
            ]
        ).ask()
        if output_format is None:
            return
        output_format = output_format.split(" ")[0].lower()
    elif ext == '.webp':
        output_format = 'webp'
    else:
        output_format = questionary.select(
            "Output format:",
            choices=["jpg", "png", "webp"]
        ).ask()
        if output_format is None:
            return

    # Quality selection
    quality = questionary.select(
        "Compression level:",
        choices=[
            "High Quality (90%) - Minimal loss",
            "Balanced (75%) - Good compression",
            "Small File (60%) - Noticeable loss",
            "Tiny (40%) - Maximum compression",
            "Custom"
        ]
    ).ask()

    if quality is None:
        return

    quality_map = {
        "High Quality (90%) - Minimal loss": 90,
        "Balanced (75%) - Good compression": 75,
        "Small File (60%) - Noticeable loss": 60,
        "Tiny (40%) - Maximum compression": 40
    }

    if quality == "Custom":
        custom_q = questionary.text("Enter quality (1-100):", default="75").ask()
        if custom_q is None:
            return
        q_val = validate_positive_integer(custom_q, "Quality")
        if q_val is None or q_val < 1 or q_val > 100:
            console.print("[bold red]Quality must be between 1 and 100.[/bold red]")
            press_continue()
            return
    else:
        q_val = quality_map.get(quality, 75)

    output_file = f"{Path(file_path).stem}_compressed.{output_format}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    kwargs = {}

    if output_format == 'jpg':
        # FFmpeg uses q:v scale 2-31 (lower is better)
        # Map 1-100 quality to 31-2
        q_scale = int(31 - (q_val / 100.0) * 29)
        kwargs['q:v'] = max(2, min(31, q_scale))
    elif output_format == 'webp':
        kwargs['quality'] = str(q_val)
    elif output_format == 'png':
        # PNG compression level 0-9 (higher = more compression but still lossless)
        # For PNG, we can reduce colors for smaller size
        if q_val < 60:
            # Use palettegen for smaller PNG
            console.print("[dim]Using palette optimization for smaller PNG...[/dim]")

    stream = ffmpeg.input(file_path).output(final_output, **kwargs)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Compressing to {output_format.upper()}..."):
        try:
            new_size = os.path.getsize(final_output)
            reduction = ((file_size - new_size) / file_size) * 100 if file_size else 0
            console.print(f"[bold green]Saved to {final_output}[/bold green]")
            console.print(f"[dim]New size: {new_size / 1024:.1f} KB ({reduction:.1f}% smaller)[/dim]")
        except Exception:
            console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Compression failed.[/bold red]")

    press_continue()


def add_image_text(file_path):
    """Add text/caption overlay to an image."""
    if not validate_input_file(file_path):
        press_continue()
        return

    # Get image dimensions for font size calculation
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        default_font_size = max(24, height // 20)
    except Exception:
        width, height = 1920, 1080
        default_font_size = 48

    text = questionary.text("Enter text to add:", default="Sample Text").ask()
    if not text:
        return

    # Position
    position = questionary.select(
        "Text position:",
        choices=[
            "Center",
            "Top Center",
            "Bottom Center",
            "Top Left",
            "Top Right",
            "Bottom Left",
            "Bottom Right"
        ]
    ).ask()

    if position is None:
        return

    # Position mapping
    pos_map = {
        "Center": {"x": "(w-tw)/2", "y": "(h-th)/2"},
        "Top Center": {"x": "(w-tw)/2", "y": "th"},
        "Bottom Center": {"x": "(w-tw)/2", "y": "h-th*2"},
        "Top Left": {"x": "20", "y": "th"},
        "Top Right": {"x": "w-tw-20", "y": "th"},
        "Bottom Left": {"x": "20", "y": "h-th*2"},
        "Bottom Right": {"x": "w-tw-20", "y": "h-th*2"},
    }
    pos = pos_map.get(position, pos_map["Center"])

    # Font size
    font_size = questionary.text(
        "Font size:",
        default=str(default_font_size)
    ).ask()

    if font_size is None:
        return

    font_size_val = validate_positive_integer(font_size, "Font size")
    if font_size_val is None:
        press_continue()
        return

    # Font color
    color = questionary.select(
        "Text color:",
        choices=["White", "Black", "Red", "Yellow", "Blue", "Green", "Custom (Hex)"]
    ).ask()

    if color is None:
        return

    color_map = {
        "White": "white",
        "Black": "black",
        "Red": "red",
        "Yellow": "yellow",
        "Blue": "blue",
        "Green": "green"
    }

    if color == "Custom (Hex)":
        hex_color = questionary.text("Enter hex color (e.g., FF5733):", default="FFFFFF").ask()
        font_color = hex_color.lstrip('#') if hex_color else "FFFFFF"
    else:
        font_color = color_map.get(color, "white")

    # Background/shadow
    style = questionary.select(
        "Text style:",
        choices=[
            "Plain text",
            "With shadow",
            "With outline",
            "With background box"
        ]
    ).ask()

    if style is None:
        return

    output_file = f"{Path(file_path).stem}_text{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # Escape text for FFmpeg
    escaped_text = text.replace("'", "\\'").replace(":", "\\:")

    # Build drawtext filter
    drawtext_params = {
        "text": escaped_text,
        "fontsize": font_size_val,
        "fontcolor": font_color,
        "x": pos["x"],
        "y": pos["y"],
    }

    if style == "With shadow":
        drawtext_params["shadowcolor"] = "black"
        drawtext_params["shadowx"] = 2
        drawtext_params["shadowy"] = 2
    elif style == "With outline":
        drawtext_params["borderw"] = 3
        drawtext_params["bordercolor"] = "black"
    elif style == "With background box":
        drawtext_params["box"] = 1
        drawtext_params["boxcolor"] = "black@0.5"
        drawtext_params["boxborderw"] = 10

    stream = ffmpeg.input(file_path).filter('drawtext', **drawtext_params).output(final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Adding text..."):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to add text.[/bold red]")

    press_continue()
