"""Advanced video features: Slideshow, Metadata Editor, Video Stabilization."""

import os
import subprocess
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console
from rich.table import Table

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, press_continue,
    get_video_duration, format_duration, check_has_video_stream
)
from peg_this.utils.ui_utils import IMAGE_EXTENSIONS

console = Console()


def create_slideshow():
    """Create a video slideshow from images."""
    console.print("[dim]Create a video from a sequence of images.[/dim]")

    # Get image directory or files
    source = questionary.select(
        "Image source:",
        choices=[
            "All images in current directory",
            "Enter specific directory path",
            "← Back"
        ]
    ).ask()

    if source == "← Back" or source is None:
        return

    if "current" in source:
        image_dir = "."
    else:
        image_dir = questionary.text(
            "Enter directory path containing images:"
        ).ask()
        if not image_dir or not os.path.isdir(image_dir):
            console.print("[bold red]Directory not found.[/bold red]")
            press_continue()
            return

    # Find images
    images = []
    for f in sorted(os.listdir(image_dir)):
        if Path(f).suffix.lower() in IMAGE_EXTENSIONS:
            images.append(os.path.join(image_dir, f))

    if not images:
        console.print("[bold red]No images found in the directory.[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Found {len(images)} images.[/dim]")

    # Duration per image
    duration = questionary.text(
        "Duration per image (seconds):",
        default="3"
    ).ask()

    if duration is None:
        return

    try:
        duration_val = float(duration)
        if duration_val <= 0:
            raise ValueError
    except ValueError:
        console.print("[bold red]Invalid duration.[/bold red]")
        press_continue()
        return

    # Transition effect
    transition = questionary.select(
        "Transition effect:",
        choices=[
            "None (Cut)",
            "Fade (Crossfade between images)",
            "← Back"
        ]
    ).ask()

    if transition == "← Back" or transition is None:
        return

    # Output resolution
    resolution = questionary.select(
        "Output resolution:",
        choices=[
            "1920x1080 (Full HD)",
            "1280x720 (HD)",
            "3840x2160 (4K)",
            "1080x1920 (Vertical/Phone)",
            "Keep original size"
        ]
    ).ask()

    if resolution is None:
        return

    # Background music (optional)
    add_music = questionary.confirm("Add background music?", default=False).ask()
    music_path = None

    if add_music:
        music_path = questionary.text("Enter path to audio file:").ask()
        if music_path and not os.path.exists(music_path):
            console.print("[yellow]Audio file not found, continuing without music.[/yellow]")
            music_path = None

    output_file = "slideshow.mp4"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # Build FFmpeg command
    # For simplicity, use concat demuxer approach
    concat_file = "slideshow_concat.txt"

    try:
        # Create concat file
        with open(concat_file, 'w') as f:
            for img in images:
                f.write(f"file '{os.path.abspath(img)}'\n")
                f.write(f"duration {duration_val}\n")
            # Add last image again for proper duration
            f.write(f"file '{os.path.abspath(images[-1])}'\n")

        # Build filter for resolution
        if "original" not in resolution.lower():
            res_parts = resolution.split(" ")[0].split("x")
            width, height = res_parts[0], res_parts[1]
            scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        else:
            scale_filter = None

        # Construct command manually for concat demuxer
        cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_file]

        if scale_filter:
            cmd.extend(['-vf', scale_filter])

        cmd.extend(['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30'])

        if music_path:
            cmd.extend(['-i', music_path, '-c:a', 'aac', '-shortest'])
        else:
            cmd.extend(['-an'])

        cmd.append(final_output)

        console.print("[bold cyan]Creating slideshow...[/bold cyan]")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(f"[bold green]Successfully created {final_output}[/bold green]")
        else:
            console.print("[bold red]Failed to create slideshow.[/bold red]")
            console.print(f"[dim]{result.stderr[:500]}[/dim]")

    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)

    press_continue()


def metadata_editor(file_path):
    """View and edit video metadata."""
    if not validate_input_file(file_path):
        press_continue()
        return

    # Get current metadata
    try:
        probe = ffmpeg.probe(file_path)
        format_info = probe.get('format', {})
        current_tags = format_info.get('tags', {})
    except ffmpeg.Error:
        console.print("[bold red]Error reading file metadata.[/bold red]")
        press_continue()
        return

    # Display current metadata
    console.print("\n[bold]Current Metadata:[/bold]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Tag", style="dim")
    table.add_column("Value")

    common_tags = ['title', 'artist', 'album', 'year', 'comment', 'genre', 'track', 'composer']

    for tag in common_tags:
        value = current_tags.get(tag, current_tags.get(tag.upper(), ""))
        if value:
            table.add_row(tag.capitalize(), str(value))

    # Show other tags
    for tag, value in current_tags.items():
        if tag.lower() not in common_tags:
            table.add_row(tag, str(value)[:50])

    console.print(table)

    action = questionary.select(
        "What would you like to do?",
        choices=[
            "Edit metadata",
            "Clear all metadata",
            "Copy metadata from another file",
            "← Back"
        ]
    ).ask()

    if action == "← Back" or action is None:
        return

    if action == "Clear all metadata":
        suffix = "no_metadata"
        output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
        action_result, final_output = check_output_file(output_file, "Output file")

        if action_result == 'cancel':
            return

        stream = ffmpeg.input(file_path).output(
            final_output,
            **{'c': 'copy', 'map_metadata': '-1'}
        )

        if action_result == 'overwrite':
            stream = stream.overwrite_output()

        if run_command(stream, "Clearing metadata...", show_progress=True):
            console.print(f"[bold green]Saved to {final_output}[/bold green]")
        else:
            console.print("[bold red]Failed to clear metadata.[/bold red]")

    elif action == "Edit metadata":
        console.print("[dim]Enter new values (leave empty to keep current):[/dim]")

        new_metadata = {}

        title = questionary.text("Title:", default=current_tags.get('title', '')).ask()
        if title:
            new_metadata['title'] = title

        artist = questionary.text("Artist:", default=current_tags.get('artist', '')).ask()
        if artist:
            new_metadata['artist'] = artist

        album = questionary.text("Album:", default=current_tags.get('album', '')).ask()
        if album:
            new_metadata['album'] = album

        year = questionary.text("Year:", default=current_tags.get('year', '')).ask()
        if year:
            new_metadata['year'] = year

        comment = questionary.text("Comment:", default=current_tags.get('comment', '')).ask()
        if comment:
            new_metadata['comment'] = comment

        if not new_metadata:
            console.print("[yellow]No changes made.[/yellow]")
            press_continue()
            return

        suffix = "edited"
        output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
        action_result, final_output = check_output_file(output_file, "Output file")

        if action_result == 'cancel':
            return

        # Build FFmpeg command with proper metadata syntax
        cmd = ['ffmpeg']
        if action_result == 'overwrite':
            cmd.append('-y')

        cmd.extend(['-i', file_path, '-c', 'copy'])

        # Add metadata arguments with correct format: -metadata key=value
        for key, value in new_metadata.items():
            cmd.extend(['-metadata', f'{key}={value}'])

        cmd.append(final_output)

        console.print("[bold cyan]Updating metadata...[/bold cyan]")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(f"[bold green]Saved to {final_output}[/bold green]")
        else:
            console.print("[bold red]Failed to update metadata.[/bold red]")
            if result.stderr:
                console.print(f"[dim]{result.stderr[:300]}[/dim]")

    elif action == "Copy metadata from another file":
        source_file = questionary.text("Enter path to source file:").ask()
        if not source_file or not os.path.exists(source_file):
            console.print("[bold red]Source file not found.[/bold red]")
            press_continue()
            return

        suffix = "metadata_copied"
        output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
        action_result, final_output = check_output_file(output_file, "Output file")

        if action_result == 'cancel':
            return

        # Use FFmpeg to copy metadata
        cmd = [
            'ffmpeg', '-y' if action_result == 'overwrite' else '-n',
            '-i', file_path,
            '-i', source_file,
            '-map', '0',
            '-map_metadata', '1',
            '-c', 'copy',
            final_output
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(f"[bold green]Saved to {final_output}[/bold green]")
        else:
            console.print("[bold red]Failed to copy metadata.[/bold red]")

    press_continue()


def stabilize_video(file_path):
    """Stabilize shaky video footage."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found.[/bold red]")
        press_continue()
        return

    console.print("[dim]Video stabilization reduces camera shake.[/dim]")
    console.print("[yellow]Note: This is a two-pass process and may take a while.[/yellow]")

    # Check if vidstab is available
    check_cmd = subprocess.run(
        ['ffmpeg', '-filters'],
        capture_output=True, text=True
    )
    if 'vidstab' not in check_cmd.stdout:
        console.print("[bold red]Error: vidstab filter not available.[/bold red]")
        console.print("[dim]You may need to install FFmpeg with vidstab support.[/dim]")
        press_continue()
        return

    strength = questionary.select(
        "Stabilization strength:",
        choices=[
            "Light (Subtle smoothing)",
            "Medium (Balanced)",
            "Heavy (Maximum stabilization)"
        ]
    ).ask()

    if strength is None:
        return

    zoom_option = questionary.select(
        "Zoom to hide black borders:",
        choices=[
            "Auto zoom (Recommended)",
            "No zoom (May show black borders)",
            "Fixed 5% zoom",
            "Fixed 10% zoom"
        ]
    ).ask()

    if zoom_option is None:
        return

    # Set parameters based on choices
    if "Light" in strength:
        shakiness = 4
        smoothing = 5
    elif "Medium" in strength:
        shakiness = 6
        smoothing = 10
    else:
        shakiness = 10
        smoothing = 20

    if "Auto" in zoom_option:
        zoom = 0
        optzoom = 1
    elif "No zoom" in zoom_option:
        zoom = 0
        optzoom = 0
    elif "5%" in zoom_option:
        zoom = 5
        optzoom = 0
    else:
        zoom = 10
        optzoom = 0

    suffix = "stabilized"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        return

    transforms_file = f"transforms_{Path(file_path).stem}.trf"

    try:
        # Pass 1: Analyze
        console.print("[bold cyan]Pass 1: Analyzing video...[/bold cyan]")
        pass1_cmd = [
            'ffmpeg', '-y', '-i', file_path,
            '-vf', f'vidstabdetect=shakiness={shakiness}:result={transforms_file}',
            '-f', 'null', '-'
        ]

        result1 = subprocess.run(pass1_cmd, capture_output=True, text=True)
        if result1.returncode != 0:
            console.print("[bold red]Analysis pass failed.[/bold red]")
            press_continue()
            return

        # Pass 2: Apply stabilization
        console.print("[bold cyan]Pass 2: Applying stabilization...[/bold cyan]")

        vidstab_filter = f"vidstabtransform=input={transforms_file}:smoothing={smoothing}:zoom={zoom}:optzoom={optzoom}"

        pass2_cmd = [
            'ffmpeg', '-y', '-i', file_path,
            '-vf', vidstab_filter,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18'
        ]

        if has_audio_stream(file_path):
            pass2_cmd.extend(['-c:a', 'copy'])

        pass2_cmd.append(final_output)

        result2 = subprocess.run(pass2_cmd, capture_output=True, text=True)

        if result2.returncode == 0:
            console.print(f"[bold green]Successfully stabilized: {final_output}[/bold green]")
        else:
            console.print("[bold red]Stabilization failed.[/bold red]")

    finally:
        if os.path.exists(transforms_file):
            os.remove(transforms_file)

    press_continue()


def create_gif_advanced(file_path):
    """Create GIF with advanced controls."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found.[/bold red]")
        press_continue()
        return

    duration = get_video_duration(file_path)
    console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

    # Time range
    use_full = questionary.confirm("Use full video length?", default=True).ask()

    start_time = 0
    end_time = duration

    if not use_full:
        start_str = questionary.text("Start time (e.g., 0, 1:30, 0:05):", default="0").ask()
        if start_str is None:
            return
        start_time = float(start_str) if start_str.replace('.', '').isdigit() else 0

        end_str = questionary.text(f"End time (max: {format_duration(duration)}):", default=str(int(duration))).ask()
        if end_str is None:
            return
        end_time = float(end_str) if end_str.replace('.', '').isdigit() else duration

    # FPS
    fps = questionary.select(
        "Frame rate (FPS):",
        choices=[
            "10 FPS (Small file, choppy)",
            "15 FPS (Balanced, recommended)",
            "20 FPS (Smooth)",
            "24 FPS (Film-like)",
            "30 FPS (Very smooth, large file)"
        ]
    ).ask()

    if fps is None:
        return

    fps_val = int(fps.split(" ")[0])

    # Size/width
    width = questionary.select(
        "Width (height auto-calculated):",
        choices=[
            "320 px (Small, fast loading)",
            "480 px (Medium, recommended)",
            "640 px (Large)",
            "800 px (HD)",
            "Original size"
        ]
    ).ask()

    if width is None:
        return

    if "Original" in width:
        width_val = -1
    else:
        width_val = int(width.split(" ")[0])

    # Quality
    quality = questionary.select(
        "Quality preset:",
        choices=[
            "Low (Smallest file)",
            "Medium (Balanced)",
            "High (Best quality, larger file)"
        ]
    ).ask()

    if quality is None:
        return

    # Loop count
    loop = questionary.select(
        "Loop behavior:",
        choices=[
            "Loop forever (default)",
            "Play once (no loop)",
            "Loop 3 times",
            "Loop 5 times"
        ]
    ).ask()

    if loop is None:
        return

    if "forever" in loop:
        loop_val = 0
    elif "once" in loop:
        loop_val = -1
    elif "3" in loop:
        loop_val = 3
    else:
        loop_val = 5

    output_file = f"{Path(file_path).stem}.gif"
    action_result, final_output = check_output_file(output_file, "GIF file")

    if action_result == 'cancel':
        return

    palette_file = f"palette_{Path(file_path).stem}.png"

    try:
        console.print("[bold cyan]Generating optimized GIF...[/bold cyan]")

        # Quality affects dithering
        if "Low" in quality:
            dither = "bayer:bayer_scale=5"
            stats_mode = "diff"
        elif "Medium" in quality:
            dither = "sierra2_4a"
            stats_mode = "diff"
        else:
            dither = "floyd_steinberg"
            stats_mode = "full"

        # Build input args
        input_args = {}
        if start_time > 0:
            input_args['ss'] = start_time
        if end_time < duration:
            input_args['t'] = end_time - start_time

        input_stream = ffmpeg.input(file_path, **input_args)

        # Build palette generation
        if width_val > 0:
            palette_stream = input_stream.video.filter('fps', fps=fps_val).filter('scale', width_val, -1, flags='lanczos').filter('palettegen', stats_mode=stats_mode)
        else:
            palette_stream = input_stream.video.filter('fps', fps=fps_val).filter('palettegen', stats_mode=stats_mode)

        run_command(palette_stream.output(palette_file).overwrite_output(), "Generating palette...")

        if not os.path.exists(palette_file):
            console.print("[bold red]Failed to generate palette.[/bold red]")
            press_continue()
            return

        # Pass 2: Create GIF
        input_stream2 = ffmpeg.input(file_path, **input_args)
        palette_input = ffmpeg.input(palette_file)

        if width_val > 0:
            video_stream = input_stream2.video.filter('fps', fps=fps_val).filter('scale', width_val, -1, flags='lanczos')
        else:
            video_stream = input_stream2.video.filter('fps', fps=fps_val)

        gif_stream = ffmpeg.filter([video_stream, palette_input], 'paletteuse', dither=dither)

        output_args = {}
        if loop_val >= 0:
            output_args['loop'] = loop_val

        output_stream = gif_stream.output(final_output, **output_args)

        if action_result == 'overwrite':
            output_stream = output_stream.overwrite_output()

        if run_command(output_stream, "Creating GIF...", show_progress=True):
            # Show file size
            size_mb = os.path.getsize(final_output) / (1024 * 1024)
            console.print(f"[bold green]Successfully created {final_output} ({size_mb:.2f} MB)[/bold green]")
        else:
            console.print("[bold red]Failed to create GIF.[/bold red]")

    finally:
        if os.path.exists(palette_file):
            os.remove(palette_file)

    press_continue()
