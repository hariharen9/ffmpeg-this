import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream, get_global_encoding_args
from peg_this.utils.validation import (
    validate_input_file, check_output_file, check_disk_space, press_continue,
    get_video_duration, format_duration, validate_time_input, check_has_video_stream
)

console = Console()


def add_watermark(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    watermark_type = questionary.select(
        "What type of watermark?",
        choices=[
            "Image (logo/PNG)",
            "Text",
            "← Back"
        ]
    ).ask()

    if watermark_type == "← Back" or watermark_type is None:
        return

    if watermark_type == "Image (logo/PNG)":
        watermark_path = questionary.text(
            "Enter path to watermark image (PNG with transparency works best):"
        ).ask()

        if not watermark_path or not os.path.exists(watermark_path):
            console.print("[bold red]Watermark file not found.[/bold red]")
            press_continue()
            return

        position = questionary.select(
            "Watermark position:",
            choices=[
                "Top-Left",
                "Top-Right",
                "Bottom-Left",
                "Bottom-Right",
                "Center"
            ]
        ).ask()

        if not position:
            return

        pos_map = {
            "Top-Left": "10:10",
            "Top-Right": "W-w-10:10",
            "Bottom-Left": "10:H-h-10",
            "Bottom-Right": "W-w-10:H-h-10",
            "Center": "(W-w)/2:(H-h)/2"
        }
        overlay_pos = pos_map.get(position, "W-w-10:H-h-10")

        scale = questionary.text(
            "Watermark scale (e.g., 0.2 for 20% of video width):",
            default="0.15"
        ).ask()

        try:
            scale_factor = float(scale)
        except ValueError:
            scale_factor = 0.15

        output_file = f"{Path(file_path).stem}_watermarked{Path(file_path).suffix}"
        action_result, final_output = check_output_file(output_file, "Video file")

        if action_result == 'cancel':
            return

        if not check_disk_space(file_path):
            return

        # Build filter: scale watermark and overlay
        main = ffmpeg.input(file_path)
        watermark = ffmpeg.input(watermark_path)

        # Scale watermark relative to video width
        watermark_scaled = watermark.filter(
            'scale', f'iw*{scale_factor}', '-1'
        )

        video = ffmpeg.overlay(main.video, watermark_scaled, x=overlay_pos.split(':')[0], y=overlay_pos.split(':')[1])

        if has_audio_stream(file_path):
            stream = ffmpeg.output(video, main.audio, final_output, **{'c:a': 'copy'})
        else:
            stream = ffmpeg.output(video, final_output)

        if action_result == 'overwrite':
            stream = stream.overwrite_output()

        if run_command(stream, "Adding watermark...", show_progress=True):
            console.print(f"[bold green]Saved to: {final_output}[/bold green]")
        else:
            console.print("[bold red]Watermark failed.[/bold red]")

    else:  # Text watermark
        text = questionary.text("Enter watermark text:", default="© My Video").ask()
        if not text:
            return

        position = questionary.select(
            "Text position:",
            choices=[
                "Top-Left",
                "Top-Right",
                "Bottom-Left",
                "Bottom-Right",
                "Center"
            ]
        ).ask()

        if not position:
            return

        pos_map = {
            "Top-Left": "x=10:y=10",
            "Top-Right": "x=w-tw-10:y=10",
            "Bottom-Left": "x=10:y=h-th-10",
            "Bottom-Right": "x=w-tw-10:y=h-th-10",
            "Center": "x=(w-tw)/2:y=(h-th)/2"
        }
        text_pos = pos_map.get(position, "x=w-tw-10:y=h-th-10")

        font_size = questionary.text("Font size:", default="24").ask()
        try:
            fs = int(font_size)
        except ValueError:
            fs = 24

        output_file = f"{Path(file_path).stem}_watermarked{Path(file_path).suffix}"
        action_result, final_output = check_output_file(output_file, "Video file")

        if action_result == 'cancel':
            return

        # Escape special characters for drawtext
        escaped_text = text.replace("'", "\\'").replace(":", "\\:")

        input_stream = ffmpeg.input(file_path)
        video = input_stream.video.filter(
            'drawtext',
            text=escaped_text,
            fontsize=fs,
            fontcolor='white',
            borderw=2,
            bordercolor='black',
            **{text_pos.split(':')[0].split('=')[0]: text_pos.split(':')[0].split('=')[1],
               text_pos.split(':')[1].split('=')[0]: text_pos.split(':')[1].split('=')[1]}
        )

        if has_audio_stream(file_path):
            stream = ffmpeg.output(video, input_stream.audio, final_output, **{'c:a': 'copy'})
        else:
            stream = ffmpeg.output(video, final_output)

        if action_result == 'overwrite':
            stream = stream.overwrite_output()

        if run_command(stream, "Adding text watermark...", show_progress=True):
            console.print(f"[bold green]Saved to: {final_output}[/bold green]")
        else:
            console.print("[bold red]Text watermark failed.[/bold red]")

    press_continue()


def merge_audio_video(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    console.print(f"[dim]Video file: {os.path.basename(file_path)}[/dim]")

    audio_path = questionary.text(
        "Enter path to audio file (mp3, wav, flac, etc.):"
    ).ask()

    if not audio_path or not os.path.exists(audio_path):
        console.print("[bold red]Audio file not found.[/bold red]")
        press_continue()
        return

    mode = questionary.select(
        "How should the audio be handled?",
        choices=[
            "Replace existing audio",
            "Mix with existing audio",
            "← Back"
        ]
    ).ask()

    if mode == "← Back" or mode is None:
        return

    output_file = f"{Path(file_path).stem}_with_audio{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        return

    video_input = ffmpeg.input(file_path)
    audio_input = ffmpeg.input(audio_path)

    if mode == "Replace existing audio":
        stream = ffmpeg.output(
            video_input.video, audio_input.audio, final_output,
            **{'c:v': 'copy', 'c:a': 'aac', 'shortest': None}
        )
    else:  # Mix
        if not has_audio_stream(file_path):
            console.print("[yellow]Video has no existing audio to mix. Using provided audio only.[/yellow]")
            stream = ffmpeg.output(
                video_input.video, audio_input.audio, final_output,
                **{'c:v': 'copy', 'c:a': 'aac', 'shortest': None}
            )
        else:
            # Mix both audio streams
            mixed = ffmpeg.filter([video_input.audio, audio_input.audio], 'amix', inputs=2)
            stream = ffmpeg.output(
                video_input.video, mixed, final_output,
                **{'c:v': 'copy', 'c:a': 'aac', 'shortest': None}
            )

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Merging audio and video...", show_progress=True):
        console.print(f"[bold green]Saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]Merge failed.[/bold red]")

    press_continue()


def video_fade(file_path):
    """Apply fade in/out effects to video."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found in the file.[/bold red]")
        press_continue()
        return

    duration = get_video_duration(file_path)

    if duration <= 0:
        console.print("[bold red]Error: Could not determine video duration.[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

    fade_type = questionary.select(
        "What type of video fade?",
        choices=[
            "Fade In (from black)",
            "Fade Out (to black)",
            "Both (fade in and out)",
            "← Back"
        ]
    ).ask()

    if fade_type == "← Back" or fade_type is None:
        return

    # Fade color
    fade_color = questionary.select(
        "Fade color:",
        choices=[
            "Black (default)",
            "White"
        ]
    ).ask()

    if fade_color is None:
        return

    color = "black" if "Black" in fade_color else "white"

    fade_in_secs = 0
    fade_out_secs = 0

    if "In" in fade_type or "Both" in fade_type:
        fade_in_dur = questionary.text(
            "Fade in duration (seconds):",
            default="1"
        ).ask()

        if fade_in_dur is None:
            return

        fade_in_secs = validate_time_input(fade_in_dur, duration, "Fade in duration")
        if fade_in_secs is None:
            press_continue()
            return

    if "Out" in fade_type or "Both" in fade_type:
        fade_out_dur = questionary.text(
            "Fade out duration (seconds):",
            default="1"
        ).ask()

        if fade_out_dur is None:
            return

        fade_out_secs = validate_time_input(fade_out_dur, duration, "Fade out duration")
        if fade_out_secs is None:
            press_continue()
            return

    suffix = "video_fade"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)
    video = input_stream.video

    # Apply fade in
    if fade_in_secs > 0:
        video = video.filter('fade', t='in', st=0, d=fade_in_secs, c=color)

    # Apply fade out
    if fade_out_secs > 0:
        start_time = duration - fade_out_secs
        video = video.filter('fade', t='out', st=start_time, d=fade_out_secs, c=color)

    if has_audio_stream(file_path):
        stream = ffmpeg.output(video, input_stream.audio, final_output, **{'c:a': 'copy'})
    else:
        stream = ffmpeg.output(video, final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Applying video fade...", show_progress=True):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to apply video fade.[/bold red]")

    press_continue()


def loop_video(file_path):
    """Loop a video multiple times or to a target duration."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found in the file.[/bold red]")
        press_continue()
        return

    duration = get_video_duration(file_path)

    if duration <= 0:
        console.print("[bold red]Error: Could not determine video duration.[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

    loop_method = questionary.select(
        "How would you like to loop?",
        choices=[
            "Loop N times",
            "Loop to target duration",
            "← Back"
        ]
    ).ask()

    if loop_method == "← Back" or loop_method is None:
        return

    loop_count = 1

    if "N times" in loop_method:
        count = questionary.text(
            "How many times to loop? (2 = play twice, 3 = play 3 times):",
            default="2"
        ).ask()

        if count is None:
            return

        try:
            loop_count = int(count)
            if loop_count < 1:
                console.print("[bold red]Loop count must be at least 1.[/bold red]")
                press_continue()
                return
        except ValueError:
            console.print("[bold red]Invalid number.[/bold red]")
            press_continue()
            return

        console.print(f"[dim]Output will be {format_duration(duration * loop_count)}[/dim]")

    else:  # Target duration
        target = questionary.text(
            "Target duration (e.g., 60 for 60 seconds, 1:30 for 90 seconds):",
            default="60"
        ).ask()

        if target is None:
            return

        target_secs = validate_time_input(target, None, "Target duration")
        if target_secs is None:
            press_continue()
            return

        # Calculate how many loops needed
        loop_count = int(target_secs / duration) + 1
        console.print(f"[dim]Will loop {loop_count} times to exceed {format_duration(target_secs)}[/dim]")

    suffix = f"looped_{loop_count}x"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # Use stream_loop for efficient looping
    input_stream = ffmpeg.input(file_path, stream_loop=loop_count - 1)

    if has_audio_stream(file_path):
        stream = ffmpeg.output(input_stream, final_output, **{'c': 'copy'})
    else:
        stream = ffmpeg.output(input_stream, final_output, **{'c:v': 'copy'})

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Looping video {loop_count} times...", show_progress=True):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to loop video.[/bold red]")

    press_continue()


def color_correction(file_path):
    """Apply color correction adjustments to video."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found in the file.[/bold red]")
        press_continue()
        return

    console.print("[dim]Adjust brightness, contrast, saturation, and gamma.[/dim]")

    mode = questionary.select(
        "Color correction mode:",
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
                "Warm (Orange/Yellow tint)",
                "Cool (Blue tint)",
                "Vibrant (High saturation)",
                "Muted (Low saturation)",
                "Vintage (Faded look)",
                "Black & White",
                "High Contrast",
                "Brighten",
                "Darken"
            ]
        ).ask()

        if preset is None:
            return

        presets = {
            "Warm (Orange/Yellow tint)": {"brightness": "0.05", "saturation": "1.2", "gamma_r": "1.1", "gamma_b": "0.9"},
            "Cool (Blue tint)": {"brightness": "0", "saturation": "1.1", "gamma_r": "0.9", "gamma_b": "1.1"},
            "Vibrant (High saturation)": {"saturation": "1.5", "contrast": "1.1"},
            "Muted (Low saturation)": {"saturation": "0.6", "contrast": "0.95"},
            "Vintage (Faded look)": {"saturation": "0.8", "contrast": "0.9", "brightness": "0.05", "gamma": "1.1"},
            "Black & White": {"saturation": "0"},
            "High Contrast": {"contrast": "1.3", "saturation": "1.1"},
            "Brighten": {"brightness": "0.1", "gamma": "1.2"},
            "Darken": {"brightness": "-0.1", "gamma": "0.85"}
        }

        eq_params = presets.get(preset, {})
        filter_desc = preset.split(" (")[0]

    else:  # Custom adjustments
        console.print("[dim]Enter values (leave empty for default):[/dim]")
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

        try:
            eq_params = {
                "brightness": brightness,
                "contrast": contrast,
                "saturation": saturation,
                "gamma": gamma
            }
        except ValueError:
            console.print("[bold red]Invalid values entered.[/bold red]")
            press_continue()
            return

        filter_desc = "Custom color correction"

    suffix = "color_corrected"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)
    video = input_stream.video.filter('eq', **eq_params)

    if has_audio_stream(file_path):
        stream = ffmpeg.output(video, input_stream.audio, final_output, **{'c:a': 'copy'})
    else:
        stream = ffmpeg.output(video, final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Applying {filter_desc}...", show_progress=True):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to apply color correction.[/bold red]")

    press_continue()


def denoise_video(file_path):
    """Reduce video noise using denoising filters."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found in the file.[/bold red]")
        press_continue()
        return

    console.print("[dim]Video denoising reduces grain and noise in footage.[/dim]")
    console.print("[yellow]Note: Denoising can be slow for long videos.[/yellow]")

    method = questionary.select(
        "Denoising method:",
        choices=[
            "hqdn3d (Fast, good quality)",
            "nlmeans (Slow, best quality)",
            "← Back"
        ]
    ).ask()

    if method == "← Back" or method is None:
        return

    strength = questionary.select(
        "Denoising strength:",
        choices=[
            "Light (Subtle, preserves detail)",
            "Medium (Balanced)",
            "Heavy (Aggressive, may lose detail)"
        ]
    ).ask()

    if strength is None:
        return

    if "hqdn3d" in method:
        if "Light" in strength:
            filter_args = {"luma_spatial": "2", "chroma_spatial": "1.5", "luma_tmp": "3", "chroma_tmp": "2"}
        elif "Medium" in strength:
            filter_args = {"luma_spatial": "4", "chroma_spatial": "3", "luma_tmp": "6", "chroma_tmp": "4"}
        else:
            filter_args = {"luma_spatial": "6", "chroma_spatial": "4.5", "luma_tmp": "9", "chroma_tmp": "6"}
        filter_name = "hqdn3d"
    else:  # nlmeans
        if "Light" in strength:
            filter_args = {"s": "3", "p": "5", "r": "9"}
        elif "Medium" in strength:
            filter_args = {"s": "5", "p": "7", "r": "11"}
        else:
            filter_args = {"s": "8", "p": "9", "r": "15"}
        filter_name = "nlmeans"

    suffix = "denoised"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)
    video = input_stream.video.filter(filter_name, **filter_args)

    if has_audio_stream(file_path):
        stream = ffmpeg.output(video, input_stream.audio, final_output, **{'c:a': 'copy'})
    else:
        stream = ffmpeg.output(video, final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    filter_desc = f"{strength.split(' ')[0]} {filter_name} denoising"
    if run_command(stream, f"Applying {filter_desc}...", show_progress=True):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to denoise video.[/bold red]")

    press_continue()


def picture_in_picture(file_path):
    """Overlay a smaller video on top of the main video."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found in the file.[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Main video: {os.path.basename(file_path)}[/dim]")

    overlay_path = questionary.text(
        "Enter path to overlay (PiP) video:"
    ).ask()

    if not overlay_path or not os.path.exists(overlay_path):
        console.print("[bold red]Overlay video not found.[/bold red]")
        press_continue()
        return

    position = questionary.select(
        "PiP position:",
        choices=[
            "Top-Left",
            "Top-Right",
            "Bottom-Left",
            "Bottom-Right",
            "Center"
        ]
    ).ask()

    if position is None:
        return

    size_percent = questionary.select(
        "PiP size (relative to main video):",
        choices=[
            "15% (Small)",
            "20% (Default)",
            "25% (Medium)",
            "30% (Large)",
            "40% (Very large)"
        ]
    ).ask()

    if size_percent is None:
        return

    scale = float(size_percent.split("%")[0]) / 100

    # Position mapping with padding
    padding = 20
    pos_map = {
        "Top-Left": (str(padding), str(padding)),
        "Top-Right": (f"main_w-overlay_w-{padding}", str(padding)),
        "Bottom-Left": (str(padding), f"main_h-overlay_h-{padding}"),
        "Bottom-Right": (f"main_w-overlay_w-{padding}", f"main_h-overlay_h-{padding}"),
        "Center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2")
    }
    x_pos, y_pos = pos_map.get(position, pos_map["Bottom-Right"])

    suffix = "pip"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    main_input = ffmpeg.input(file_path)
    overlay_input = ffmpeg.input(overlay_path)

    # Scale overlay video
    overlay_scaled = overlay_input.video.filter('scale', f"iw*{scale}", f"ih*{scale}")

    # Overlay on main video
    video = ffmpeg.overlay(main_input.video, overlay_scaled, x=x_pos, y=y_pos, shortest=1)

    if has_audio_stream(file_path):
        stream = ffmpeg.output(video, main_input.audio, final_output, **{'c:a': 'copy'})
    else:
        stream = ffmpeg.output(video, final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Creating picture-in-picture...", show_progress=True):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to create picture-in-picture.[/bold red]")

    press_continue()


def blur_region(file_path):
    """Apply blur or pixelate effect to selected regions of video."""
    try:
        import tkinter as tk
        from PIL import Image, ImageTk
    except ImportError:
        console.print("[bold red]Cannot perform visual selection: tkinter & Pillow are not installed.[/bold red]")
        console.print("[dim]Install them with: pip install tk Pillow[/dim]")
        press_continue()
        return

    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found in the file.[/bold red]")
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration <= 0:
        console.print("[bold red]Error: Could not determine video duration.[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")
    console.print("[dim]Apply blur or pixelate effect to selected regions.[/dim]")

    # Select effect type
    effect_type = questionary.select(
        "Select effect type:",
        choices=[
            "Blur (Gaussian blur)",
            "Pixelate (Mosaic/Block effect)",
            "← Back"
        ]
    ).ask()

    if effect_type == "← Back" or effect_type is None:
        return

    is_blur = "Blur" in effect_type

    # Effect strength
    strength = questionary.select(
        f"{'Blur' if is_blur else 'Pixelate'} strength:",
        choices=[
            "Light",
            "Medium (Recommended)",
            "Heavy",
            "Extreme (Almost unrecognizable)"
        ]
    ).ask()

    if strength is None:
        return

    # Time range options
    time_mode = questionary.select(
        "Apply effect for:",
        choices=[
            "Entire video",
            "Specific time range",
            "← Back"
        ]
    ).ask()

    if time_mode == "← Back" or time_mode is None:
        return

    start_time = 0
    end_time = duration

    if "Specific" in time_mode:
        console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

        start_str = questionary.text(
            "Start time (e.g., 0, 1:30, 0:05):",
            default="0"
        ).ask()

        if start_str is None:
            return

        start_time = validate_time_input(start_str, duration, "Start time")
        if start_time is None:
            press_continue()
            return

        end_str = questionary.text(
            f"End time (max: {format_duration(duration)}):",
            default=format_duration(duration)
        ).ask()

        if end_str is None:
            return

        end_time = validate_time_input(end_str, duration, "End time")
        if end_time is None:
            press_continue()
            return

        if end_time <= start_time:
            console.print("[bold red]End time must be after start time.[/bold red]")
            press_continue()
            return

    # Extract preview frame
    import tempfile
    preview_fd, preview_frame = tempfile.mkstemp(suffix=".jpg")
    os.close(preview_fd)

    try:
        # Get frame from the middle of the effect time range
        preview_time = start_time + (end_time - start_time) / 2

        run_command(
            ffmpeg.input(file_path, ss=preview_time).output(preview_frame, vframes=1, **{'q:v': 2}).overwrite_output(),
            "Extracting preview frame..."
        )

        if not os.path.exists(preview_frame):
            console.print("[bold red]Could not extract a frame from the video.[/bold red]")
            press_continue()
            return

        # Get video dimensions
        probe = ffmpeg.probe(file_path)
        video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        if not video_stream:
            console.print("[bold red]Could not get video dimensions.[/bold red]")
            press_continue()
            return

        video_width = int(video_stream['width'])
        video_height = int(video_stream['height'])

        # Visual region selection with Tkinter
        regions = []
        root = tk.Tk()
        root.title("Blur/Pixelate - Draw rectangles, press 'u' to undo, close when done")
        root.attributes("-topmost", True)

        img = Image.open(preview_frame)

        # Calculate scale factor for display
        max_display_width = min(root.winfo_screenwidth() - 100, video_width)
        max_display_height = min(root.winfo_screenheight() - 150, video_height)

        display_scale = min(max_display_width / video_width, max_display_height / video_height, 1.0)
        display_width = int(video_width * display_scale)
        display_height = int(video_height * display_scale)

        if display_scale < 1.0:
            img = img.resize((display_width, display_height), Image.Resampling.LANCZOS)

        img_tk = ImageTk.PhotoImage(img, master=root)

        # Main frame
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for drawing
        canvas = tk.Canvas(main_frame, width=display_width, height=display_height, cursor="cross")
        canvas.pack()
        canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)

        # Instructions frame
        instructions = tk.Frame(root)
        instructions.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(
            instructions,
            text="Draw rectangles to select regions. Press 'u' to undo. Close window when done.",
            font=("Arial", 10)
        ).pack()

        # Status label
        status_var = tk.StringVar(value="Regions: 0")
        status_label = tk.Label(instructions, textvariable=status_var, font=("Arial", 10, "bold"))
        status_label.pack()

        # Done button
        def on_done():
            root.quit()
            root.destroy()

        done_btn = tk.Button(instructions, text="Done - Apply Effect", command=on_done,
                            bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), padx=20, pady=5)
        done_btn.pack(pady=10)

        rect_data = {"current_rect": None, "start_x": 0, "start_y": 0}
        drawn_rects = []

        def on_press(event):
            rect_data["start_x"] = event.x
            rect_data["start_y"] = event.y
            rect_data["current_rect"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline='red', width=2, dash=(4, 2)
            )

        def on_drag(event):
            if rect_data["current_rect"]:
                canvas.coords(
                    rect_data["current_rect"],
                    rect_data["start_x"], rect_data["start_y"],
                    event.x, event.y
                )

        def on_release(event):
            if rect_data["current_rect"]:
                x1, y1 = rect_data["start_x"], rect_data["start_y"]
                x2, y2 = event.x, event.y

                # Normalize coordinates
                x1, x2 = min(x1, x2), max(x1, x2)
                y1, y2 = min(y1, y2), max(y1, y2)

                # Check minimum size
                if (x2 - x1) >= 10 and (y2 - y1) >= 10:
                    # Convert to actual video coordinates
                    actual_x1 = int(x1 / display_scale)
                    actual_y1 = int(y1 / display_scale)
                    actual_x2 = int(x2 / display_scale)
                    actual_y2 = int(y2 / display_scale)

                    # Clamp to video bounds
                    actual_x1 = max(0, min(actual_x1, video_width))
                    actual_y1 = max(0, min(actual_y1, video_height))
                    actual_x2 = max(0, min(actual_x2, video_width))
                    actual_y2 = max(0, min(actual_y2, video_height))

                    regions.append({
                        "x": actual_x1,
                        "y": actual_y1,
                        "w": actual_x2 - actual_x1,
                        "h": actual_y2 - actual_y1
                    })

                    # Update rectangle to solid line
                    canvas.delete(rect_data["current_rect"])
                    final_rect = canvas.create_rectangle(
                        x1, y1, x2, y2,
                        outline='green', width=2
                    )
                    drawn_rects.append(final_rect)

                    # Add region number label
                    label = canvas.create_text(
                        x1 + 5, y1 + 5,
                        text=str(len(regions)),
                        anchor=tk.NW,
                        fill='green',
                        font=('Arial', 12, 'bold')
                    )
                    drawn_rects.append(label)

                    status_var.set(f"Regions: {len(regions)}")
                else:
                    canvas.delete(rect_data["current_rect"])

                rect_data["current_rect"] = None

        def undo_last(event=None):
            if regions and len(drawn_rects) >= 2:
                regions.pop()
                canvas.delete(drawn_rects.pop())
                canvas.delete(drawn_rects.pop())
                status_var.set(f"Regions: {len(regions)}")

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        root.bind("u", undo_last)
        root.bind("U", undo_last)
        root.bind("<Return>", lambda e: on_done())
        root.bind("<Escape>", lambda e: on_done())
        root.protocol("WM_DELETE_WINDOW", on_done)

        console.print("[bold cyan]Instructions: Draw rectangles around areas to blur/pixelate. Press 'u' to undo. Click 'Done' or press Enter when finished.[/bold cyan]")

        root.lift()
        root.after_idle(root.attributes, '-topmost', False)
        root.mainloop()

        if not regions:
            console.print("[bold yellow]No regions selected. Operation cancelled.[/bold yellow]")
            return

        console.print(f"[dim]Selected {len(regions)} region(s) to process.[/dim]")

        # Set strength parameters
        if is_blur:
            strength_map = {
                "Light": 10,
                "Medium (Recommended)": 20,
                "Heavy": 40,
                "Extreme (Almost unrecognizable)": 80
            }
            blur_amount = strength_map.get(strength, 20)
        else:
            strength_map = {
                "Light": 8,
                "Medium (Recommended)": 16,
                "Heavy": 32,
                "Extreme (Almost unrecognizable)": 64
            }
            pixel_size = strength_map.get(strength, 16)

        suffix = "blurred" if is_blur else "pixelated"
        output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
        action_result, final_output = check_output_file(output_file, "Output file")

        if action_result == 'cancel':
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        # Build FFmpeg filter chain for multiple regions
        # Strategy: For each region, crop -> blur -> overlay back
        import subprocess

        filter_complex_parts = []
        last_video = "[0:v]"
        valid_region_count = 0

        # Determine enable expression for time-based effect
        # Note: In filter_complex, commas in expressions don't need escaping when using quotes
        if "Specific" in time_mode:
            enable_expr = f"between(t,{start_time},{end_time})"
        else:
            enable_expr = None

        for region in regions:
            x, y, w, h = region['x'], region['y'], region['w'], region['h']

            # Clamp to video bounds first
            x = max(0, min(x, video_width - 2))
            y = max(0, min(y, video_height - 2))
            w = max(2, min(w, video_width - x))
            h = max(2, min(h, video_height - y))

            # Ensure dimensions are even (required by video encoders)
            # Reduce by 1 if odd (to stay within bounds)
            w = w if w % 2 == 0 else w - 1
            h = h if h % 2 == 0 else h - 1

            # Skip if dimensions are too small
            if w < 2 or h < 2:
                continue

            i = valid_region_count
            valid_region_count += 1

            if is_blur:
                effect_filter = f"boxblur={blur_amount}:{blur_amount}"
            else:
                # True pixelate: scale down then up with nearest neighbor
                scale_factor = max(2, pixel_size // 4)
                down_w = max(4, w // scale_factor)
                down_h = max(4, h // scale_factor)
                # Make sure scaled dimensions are even
                down_w = down_w if down_w % 2 == 0 else down_w + 1
                down_h = down_h if down_h % 2 == 0 else down_h + 1
                effect_filter = f"scale={down_w}:{down_h},scale={w}:{h}:flags=neighbor"

            if enable_expr:
                # Time-based: overlay with enable
                # Note: enable expression needs escaped quotes for FFmpeg filter parsing
                filter_complex_parts.append(
                    f"{last_video}split[main{i}][copy{i}];"
                    f"[copy{i}]crop={w}:{h}:{x}:{y},{effect_filter}[blur{i}];"
                    f"[main{i}][blur{i}]overlay={x}:{y}:enable='{enable_expr}'[out{i}]"
                )
            else:
                # Full video: crop, effect, overlay
                filter_complex_parts.append(
                    f"{last_video}split[main{i}][copy{i}];"
                    f"[copy{i}]crop={w}:{h}:{x}:{y},{effect_filter}[blur{i}];"
                    f"[main{i}][blur{i}]overlay={x}:{y}[out{i}]"
                )

            last_video = f"[out{i}]"

        # Check if any valid regions were processed
        if valid_region_count == 0:
            console.print("[bold yellow]No valid regions after processing. Operation cancelled.[/bold yellow]")
            press_continue()
            return

        filter_complex = ";".join(filter_complex_parts)

        # Build FFmpeg command
        cmd = ['ffmpeg']
        if action_result == 'overwrite':
            cmd.append('-y')

        cmd.extend(['-i', file_path])
        cmd.extend(['-filter_complex', filter_complex])
        cmd.extend(['-map', last_video])

        if has_audio_stream(file_path):
            cmd.extend(['-map', '0:a', '-c:a', 'copy'])

        # Use global encoding args
        from peg_this.settings import Settings
        settings = Settings()
        encoding_args = settings.get_encoder_list_args(quality="medium", crf=18)
        cmd.extend(encoding_args)

        cmd.append(final_output)

        console.print(f"[bold cyan]Applying {'blur' if is_blur else 'pixelate'} to {valid_region_count} region(s)...[/bold cyan]")

        # Debug: show filter info
        console.print(f"[dim]Video: {video_width}x{video_height}[/dim]")
        for i, region in enumerate(regions):
            console.print(f"[dim]Region {i+1}: x={region['x']}, y={region['y']}, w={region['w']}, h={region['h']}[/dim]")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
        else:
            console.print("[bold red]Failed to apply effect.[/bold red]")
            if result.stderr:
                # Find the actual error line (usually after "Error" or at the end)
                error_lines = result.stderr.strip().split('\n')
                # Look for lines containing "Error" or get last few lines
                error_found = [l for l in error_lines if 'Error' in l or 'error' in l or 'Invalid' in l]
                if error_found:
                    error_msg = '\n'.join(error_found[-3:])
                else:
                    error_msg = '\n'.join(error_lines[-5:])
                console.print(f"[dim]{error_msg}[/dim]")

    except Exception as e:
        console.print(f"[bold red]An error occurred: {e}[/bold red]")
    finally:
        if os.path.exists(preview_frame):
            os.remove(preview_frame)
        press_continue()


def auto_blur_faces(file_path):
    """Automatically detect and blur faces in video using AI."""
    # Check for required dependencies
    try:
        import cv2
        import mediapipe as mp
        import numpy as np
    except ImportError as e:
        missing = str(e).split("'")[1] if "'" in str(e) else "required packages"
        console.print(f"[bold red]Missing dependency: {missing}[/bold red]")
        console.print("[dim]Install with: pip install opencv-python mediapipe[/dim]")
        press_continue()
        return

    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found in the file.[/bold red]")
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration <= 0:
        console.print("[bold red]Error: Could not determine video duration.[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")
    console.print("[bold cyan]AI-powered face detection and blur[/bold cyan]")

    # Detection method
    method = questionary.select(
        "Detection method:",
        choices=[
            "OpenCV Haar Cascade (Fast, works at all distances)",
            "MediaPipe AI (More accurate for close-up faces)",
            "← Back"
        ]
    ).ask()

    if method == "← Back" or method is None:
        return

    use_mediapipe = "MediaPipe" in method

    # Detection confidence
    confidence = questionary.select(
        "Face detection sensitivity:",
        choices=[
            "High (Detect more faces, may have false positives)",
            "Medium (Balanced, recommended)",
            "Low (Only very clear faces)"
        ]
    ).ask()

    if confidence is None:
        return

    if "High" in confidence:
        min_confidence = 0.2
    elif "Medium" in confidence:
        min_confidence = 0.4
    else:
        min_confidence = 0.6

    # Blur strength
    blur_strength = questionary.select(
        "Blur strength:",
        choices=[
            "Light (Face slightly obscured)",
            "Medium (Recommended)",
            "Heavy (Face unrecognizable)",
            "Pixelate (Mosaic effect)"
        ]
    ).ask()

    if blur_strength is None:
        return

    # Blur padding (expand blur region around face)
    padding = questionary.select(
        "Blur region padding:",
        choices=[
            "None (Exact face boundary)",
            "Small (10% padding)",
            "Medium (20% padding, recommended)",
            "Large (30% padding)"
        ]
    ).ask()

    if padding is None:
        return

    if "None" in padding:
        padding_pct = 0.0
    elif "Small" in padding:
        padding_pct = 0.1
    elif "Medium" in padding:
        padding_pct = 0.2
    else:
        padding_pct = 0.3

    suffix = "faces_blurred"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # Temporary file for video without audio
    import tempfile
    temp_dir_path = tempfile.gettempdir()
    temp_video = os.path.join(temp_dir_path, f"temp_video_{Path(file_path).stem}.mp4")

    cap = None
    out = None
    detector = None

    try:
        # Open video
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            console.print("[bold red]Error: Could not open video file.[/bold red]")
            press_continue()
            return

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        console.print(f"[dim]Resolution: {width}x{height}, FPS: {fps:.2f}, Frames: {total_frames}[/dim]")

        # Set up video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

        # Progress tracking
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

        # Initialize face detector based on method
        face_cascade = None

        if use_mediapipe:
            # Initialize MediaPipe Face Detection using Tasks API
            import urllib.request
            import urllib.error
            import ssl
            model_path = os.path.join(temp_dir_path, "blaze_face_short_range.tflite")

            if not os.path.exists(model_path):
                console.print("[dim]Downloading face detection model from Google...[/dim]")
                model_url = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"

                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                try:
                    with urllib.request.urlopen(model_url, context=ssl_context, timeout=30) as response:
                        with open(model_path, 'wb') as f:
                            f.write(response.read())
                    console.print("[dim]Model downloaded successfully.[/dim]")
                except Exception as e:
                    console.print(f"[bold red]Failed to download model: {e}[/bold red]")
                    console.print("[yellow]Falling back to OpenCV Haar Cascade...[/yellow]")
                    use_mediapipe = False

            if use_mediapipe:
                BaseOptions = mp.tasks.BaseOptions
                FaceDetector = mp.tasks.vision.FaceDetector
                FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
                VisionRunningMode = mp.tasks.vision.RunningMode

                options = FaceDetectorOptions(
                    base_options=BaseOptions(model_asset_path=model_path),
                    running_mode=VisionRunningMode.IMAGE,
                    min_detection_confidence=min_confidence
                )
                detector = FaceDetector.create_from_options(options)

        if not use_mediapipe:
            # Use OpenCV Haar Cascade (built-in, works at all distances)
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            face_cascade = cv2.CascadeClassifier(cascade_path)
            if face_cascade.empty():
                console.print("[bold red]Error: Could not load face cascade.[/bold red]")
                press_continue()
                return

            # Map confidence to scale factor and neighbors
            if "High" in confidence:
                scale_factor = 1.1
                min_neighbors = 3
            elif "Medium" in confidence:
                scale_factor = 1.2
                min_neighbors = 5
            else:
                scale_factor = 1.3
                min_neighbors = 7

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Processing frames...", total=total_frames)
            faces_detected = 0
            frames_with_faces = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                face_boxes = []

                if use_mediapipe and detector:
                    # MediaPipe detection
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                    detection_result = detector.detect(mp_image)

                    if detection_result.detections:
                        for detection in detection_result.detections:
                            bbox = detection.bounding_box
                            face_boxes.append((bbox.origin_x, bbox.origin_y, bbox.width, bbox.height))
                else:
                    # OpenCV Haar Cascade detection
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(
                        gray,
                        scaleFactor=scale_factor,
                        minNeighbors=min_neighbors,
                        minSize=(30, 30)
                    )
                    for (x, y, w, h) in faces:
                        face_boxes.append((x, y, w, h))

                if face_boxes:
                    frames_with_faces += 1
                    for (x, y, w, h) in face_boxes:
                        faces_detected += 1

                        # Apply padding
                        pad_w = int(w * padding_pct)
                        pad_h = int(h * padding_pct)
                        x = max(0, x - pad_w)
                        y = max(0, y - pad_h)
                        w = min(width - x, w + 2 * pad_w)
                        h = min(height - y, h + 2 * pad_h)

                        # Extract face region
                        face_region = frame[y:y+h, x:x+w]

                        if face_region.size > 0:
                            # Apply blur based on strength
                            if "Light" in blur_strength:
                                blurred = cv2.GaussianBlur(face_region, (31, 31), 20)
                            elif "Medium" in blur_strength:
                                blurred = cv2.GaussianBlur(face_region, (71, 71), 50)
                            elif "Heavy" in blur_strength:
                                blurred = cv2.GaussianBlur(face_region, (151, 151), 100)
                            else:  # Pixelate
                                small = cv2.resize(face_region, (max(1, w // 16), max(1, h // 16)), interpolation=cv2.INTER_LINEAR)
                                blurred = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

                            # Replace face region with blurred version
                            frame[y:y+h, x:x+w] = blurred

                out.write(frame)
                progress.update(task, advance=1)

        console.print(f"[dim]Detected {faces_detected} face instances across {frames_with_faces} frames.[/dim]")

        if faces_detected == 0:
            console.print("[yellow]No faces detected in the video.[/yellow]")
            return

        # Merge with original audio using FFmpeg
        console.print("[bold cyan]Merging audio...[/bold cyan]")

        from peg_this.settings import Settings
        settings = Settings()
        encoding_args = settings.get_encoder_list_args(quality="medium", crf=18)

        if has_audio_stream(file_path):
            # Combine processed video with original audio
            import subprocess
            merge_cmd = [
                'ffmpeg', '-y',
                '-i', temp_video,
                '-i', file_path,
            ]
            merge_cmd.extend(encoding_args)
            merge_cmd.extend([
                '-c:a', 'aac', '-b:a', '192k',
                '-map', '0:v:0', '-map', '1:a:0',
                '-shortest',
                final_output
            ])
            result = subprocess.run(merge_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                console.print("[bold red]Error merging audio.[/bold red]")
                console.print(f"[dim]{result.stderr[-300:] if result.stderr else 'Unknown error'}[/dim]")
            else:
                console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
        else:
            # No audio, just re-encode with better codec
            import subprocess
            encode_cmd = [
                'ffmpeg', '-y',
                '-i', temp_video,
            ]
            encode_cmd.extend(encoding_args)
            encode_cmd.append(final_output)

            result = subprocess.run(encode_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
            else:
                console.print("[bold red]Error encoding video.[/bold red]")

    except Exception as e:
        console.print(f"[bold red]An error occurred: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
    finally:
        # Clean up detector
        if detector:
            detector.close()
        if cap:
            cap.release()
        if out:
            out.release()
        # Clean up temp file
        if os.path.exists(temp_video):
            try:
                os.remove(temp_video)
            except Exception:
                pass
        press_continue()


def audio_visualizer(file_path):
    """Generate a visualization video from audio or video file."""
    import subprocess

    if not validate_input_file(file_path):
        press_continue()
        return

    # Check if file has audio
    if not has_audio_stream(file_path):
        console.print("[bold red]Error: No audio stream found in the file.[/bold red]")
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration <= 0:
        console.print("[bold red]Error: Could not determine file duration.[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Duration: {format_duration(duration)}[/dim]")
    console.print("[bold cyan]Audio Visualizer - Create stunning visualizations[/bold cyan]")

    # Visualization style
    style = questionary.select(
        "Visualization style:",
        choices=[
            "Spectrum Bars (Classic equalizer bars)",
            "Waveform (Oscilloscope wave)",
            "Showcase CQT (Musical frequency analyzer - Pro look)",
            "Spectrogram (Frequency waterfall)",
            "Vector Scope (Circular stereo display)",
            "Audio Histogram (Frequency histogram)",
            "← Back"
        ]
    ).ask()

    if style == "← Back" or style is None:
        return

    # Resolution
    resolution = questionary.select(
        "Output resolution:",
        choices=[
            "1920x1080 (Full HD)",
            "1280x720 (HD)",
            "3840x2160 (4K)",
            "1080x1920 (Vertical/Phone)",
            "1080x1080 (Square/Instagram)"
        ]
    ).ask()

    if resolution is None:
        return

    res_parts = resolution.split(" ")[0].split("x")
    width, height = int(res_parts[0]), int(res_parts[1])

    # Color scheme
    color_scheme = questionary.select(
        "Color scheme:",
        choices=[
            "Neon (Cyan/Magenta)",
            "Fire (Red/Orange/Yellow)",
            "Ocean (Blue/Cyan)",
            "Matrix (Green)",
            "Rainbow (Full spectrum)",
            "Monochrome (White)"
        ]
    ).ask()

    if color_scheme is None:
        return

    # Background
    background = questionary.select(
        "Background:",
        choices=[
            "Black",
            "Dark Gray",
            "Gradient (Dark)",
            "Transparent (if supported)"
        ]
    ).ask()

    if background is None:
        return

    # Build FFmpeg filter based on style
    filter_complex = None
    bg_color = "0x000000" if "Black" in background else "0x1a1a1a" if "Gray" in background else "0x000000"

    if "Spectrum Bars" in style:
        # showspectrum with bars mode
        if "Neon" in color_scheme:
            color = "channel"
        elif "Fire" in color_scheme:
            color = "fire"
        elif "Ocean" in color_scheme:
            color = "cool"
        elif "Matrix" in color_scheme:
            color = "green"
        elif "Rainbow" in color_scheme:
            color = "rainbow"
        else:
            color = "white"

        filter_complex = (
            f"[0:a]showspectrum=s={width}x{height}:mode=combined:color={color}:"
            f"scale=cbrt:fscale=log:saturation=3:slide=scroll[v]"
        )

    elif "Waveform" in style:
        # showwaves
        if "Neon" in color_scheme:
            colors = "0x00ffff|0xff00ff"
        elif "Fire" in color_scheme:
            colors = "0xff0000|0xff8800|0xffff00"
        elif "Ocean" in color_scheme:
            colors = "0x0066ff|0x00ccff"
        elif "Matrix" in color_scheme:
            colors = "0x00ff00"
        elif "Rainbow" in color_scheme:
            colors = "0xff0000|0xff8800|0xffff00|0x00ff00|0x0088ff|0x8800ff"
        else:
            colors = "0xffffff"

        filter_complex = (
            f"[0:a]showwaves=s={width}x{height}:mode=cline:rate=30:colors={colors}:"
            f"scale=cbrt[v]"
        )

    elif "CQT" in style:
        # showcqt - constant Q transform, looks professional
        if "Neon" in color_scheme:
            bar_g = 2
            sono_g = 4
        elif "Fire" in color_scheme:
            bar_g = 3
            sono_g = 3
        elif "Ocean" in color_scheme:
            bar_g = 1
            sono_g = 4
        elif "Matrix" in color_scheme:
            bar_g = 2
            sono_g = 3
        else:
            bar_g = 2
            sono_g = 4

        filter_complex = (
            f"[0:a]showcqt=s={width}x{height}:bar_g={bar_g}:sono_g={sono_g}:"
            f"bar_v=10:sono_v=bar_v:tc=0.33:attack=0.033:tlength=1[v]"
        )

    elif "Spectrogram" in style:
        # showspectrum in separate mode
        if "Neon" in color_scheme:
            color = "channel"
        elif "Fire" in color_scheme:
            color = "fire"
        elif "Ocean" in color_scheme:
            color = "cool"
        elif "Matrix" in color_scheme:
            color = "green"
        elif "Rainbow" in color_scheme:
            color = "rainbow"
        else:
            color = "intensity"

        filter_complex = (
            f"[0:a]showspectrum=s={width}x{height}:mode=separate:color={color}:"
            f"scale=log:fscale=log:slide=fullframe:saturation=2[v]"
        )

    elif "Vector" in style:
        # avectorscope
        if "Neon" in color_scheme:
            mode = "lissajous"
            draw = "line"
        elif "Fire" in color_scheme:
            mode = "polar"
            draw = "dot"
        elif "Matrix" in color_scheme:
            mode = "lissajous_xy"
            draw = "line"
        else:
            mode = "lissajous"
            draw = "line"

        filter_complex = (
            f"[0:a]avectorscope=s={width}x{height}:mode={mode}:draw={draw}:"
            f"scale=cbrt:rate=30[v]"
        )

    elif "Histogram" in style:
        # ahistogram
        if "Neon" in color_scheme:
            dmode = "separate"
        else:
            dmode = "single"

        filter_complex = (
            f"[0:a]ahistogram=s={width}x{height}:dmode={dmode}:rate=30:"
            f"scale=log:slide=scroll[v]"
        )

    if not filter_complex:
        console.print("[bold red]Error: Unknown visualization style.[/bold red]")
        press_continue()
        return

    suffix = "visualizer"
    output_file = f"{Path(file_path).stem}_{suffix}.mp4"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # Build FFmpeg command
    cmd = ['ffmpeg']
    if action_result == 'overwrite':
        cmd.append('-y')

    cmd.extend(['-i', file_path])
    cmd.extend(['-filter_complex', filter_complex])
    cmd.extend(['-map', '[v]', '-map', '0:a'])

    # Use global encoding args
    from peg_this.settings import Settings
    settings = Settings()
    encoding_args = settings.get_encoder_list_args(quality="medium", crf=18)
    cmd.extend(encoding_args)

    cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
    cmd.extend(['-pix_fmt', 'yuv420p'])
    cmd.extend(['-r', '30'])
    cmd.append(final_output)

    console.print(f"[bold cyan]Generating {style.split(' (')[0]} visualization...[/bold cyan]")
    console.print("[dim]This may take a while for long audio files.[/dim]")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        console.print(f"[bold green]Successfully created {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to create visualization.[/bold red]")
        if result.stderr:
            error_lines = result.stderr.strip().split('\n')
            error_found = [l for l in error_lines if 'Error' in l or 'error' in l]
            if error_found:
                console.print(f"[dim]{error_found[-1]}[/dim]")
            else:
                console.print(f"[dim]{error_lines[-3:]}[/dim]")

    press_continue()


def rotate_video(file_path):
    """Rotate video by 90, 180, or 270 degrees."""
    if not validate_input_file(file_path):
        press_continue()
        return

    rotation = questionary.select(
        "Select rotation:",
        choices=[
            "90° Clockwise",
            "90° Counter-Clockwise",
            "180°",
            "← Back"
        ]
    ).ask()

    if rotation == "← Back" or rotation is None:
        return

    # FFmpeg transpose values:
    # 0 = 90° counter-clockwise and vertical flip
    # 1 = 90° clockwise
    # 2 = 90° counter-clockwise
    # 3 = 90° clockwise and vertical flip
    if rotation == "90° Clockwise":
        transpose_value = "1"
        suffix = "rotated_90cw"
    elif rotation == "90° Counter-Clockwise":
        transpose_value = "2"
        suffix = "rotated_90ccw"
    else:  # 180°
        transpose_value = None
        suffix = "rotated_180"

    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        return

    if not check_disk_space(file_path):
        return

    try:
        stream = ffmpeg.input(file_path)

        if transpose_value:
            # 90° rotation
            video = stream.video.filter('transpose', transpose_value)
        else:
            # 180° rotation = two 90° rotations or hflip+vflip
            video = stream.video.filter('hflip').filter('vflip')

        if has_audio_stream(file_path):
            output = ffmpeg.output(video, stream.audio, final_output, **{'c:a': 'copy'})
        else:
            output = ffmpeg.output(video, final_output)

        console.print(f"[bold cyan]Rotating video {rotation}...[/bold cyan]")
        run_command(output, action_result == 'overwrite')
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    except ffmpeg.Error as e:
        console.print(f"[bold red]FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}[/bold red]")

    press_continue()


def flip_video(file_path):
    """Flip video horizontally or vertically."""
    if not validate_input_file(file_path):
        press_continue()
        return

    flip_type = questionary.select(
        "Select flip direction:",
        choices=[
            "Horizontal (Mirror)",
            "Vertical",
            "← Back"
        ]
    ).ask()

    if flip_type == "← Back" or flip_type is None:
        return

    if flip_type == "Horizontal (Mirror)":
        filter_name = "hflip"
        suffix = "flipped_h"
    else:
        filter_name = "vflip"
        suffix = "flipped_v"

    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        return

    if not check_disk_space(file_path):
        return

    try:
        stream = ffmpeg.input(file_path)
        video = stream.video.filter(filter_name)

        if has_audio_stream(file_path):
            output = ffmpeg.output(video, stream.audio, final_output, **{'c:a': 'copy'})
        else:
            output = ffmpeg.output(video, final_output)

        console.print(f"[bold cyan]Flipping video {flip_type.lower()}...[/bold cyan]")
        run_command(output, action_result == 'overwrite')
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    except ffmpeg.Error as e:
        console.print(f"[bold red]FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}[/bold red]")

    press_continue()


def remove_background(file_path):
    """Remove background from image or video using AI (rembg)."""
    if not validate_input_file(file_path):
        press_continue()
        return

    # Check if it's an image or video
    ext = Path(file_path).suffix.lower()
    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'}
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}

    if ext in image_exts:
        remove_background_image(file_path)
    elif ext in video_exts:
        remove_background_video(file_path)
    else:
        console.print(f"[bold red]Unsupported file format: {ext}[/bold red]")
        console.print("[dim]Supported: JPG, PNG, WebP, BMP, TIFF (images) or MP4, MKV, AVI, MOV, WebM (videos)[/dim]")
        press_continue()


def remove_background_image(file_path):
    """Remove background from a single image."""
    try:
        from rembg import remove
        from PIL import Image
    except ImportError:
        console.print("[bold red]Error: rembg is not installed.[/bold red]")
        console.print("[yellow]Install it with: pip install rembg onnxruntime[/yellow]")
        press_continue()
        return

    bg_option = questionary.select(
        "What should replace the background?",
        choices=[
            "Transparent (PNG)",
            "Solid Color",
            "Custom Image",
            "← Back"
        ]
    ).ask()

    if bg_option == "← Back" or bg_option is None:
        return

    bg_color = None
    bg_image_path = None

    if bg_option == "Solid Color":
        color_choice = questionary.select(
            "Select background color:",
            choices=[
                "White",
                "Black",
                "Green (Chroma Key)",
                "Blue (Chroma Key)",
                "Custom (Hex)"
            ]
        ).ask()

        if not color_choice:
            return

        color_map = {
            "White": (255, 255, 255),
            "Black": (0, 0, 0),
            "Green (Chroma Key)": (0, 255, 0),
            "Blue (Chroma Key)": (0, 0, 255)
        }

        if color_choice == "Custom (Hex)":
            hex_color = questionary.text(
                "Enter hex color (e.g., #FF5733 or FF5733):"
            ).ask()
            if hex_color:
                hex_color = hex_color.lstrip('#')
                try:
                    bg_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                except ValueError:
                    console.print("[yellow]Invalid hex color, using white.[/yellow]")
                    bg_color = (255, 255, 255)
            else:
                bg_color = (255, 255, 255)
        else:
            bg_color = color_map.get(color_choice, (255, 255, 255))

    elif bg_option == "Custom Image":
        bg_image_path = questionary.text(
            "Enter path to background image:"
        ).ask()
        if not bg_image_path or not os.path.exists(bg_image_path):
            console.print("[bold red]Background image not found.[/bold red]")
            press_continue()
            return

    # Determine output format
    if bg_option == "Transparent (PNG)":
        output_ext = ".png"
        suffix = "nobg"
    else:
        output_ext = Path(file_path).suffix
        suffix = "nobg"

    output_file = f"{Path(file_path).stem}_{suffix}{output_ext}"
    action_result, final_output = check_output_file(output_file, "Image file")

    if action_result == 'cancel':
        return

    console.print("[bold cyan]Removing background (this may take a moment on first run)...[/bold cyan]")
    console.print("[dim]First run will download the AI model (~170MB)[/dim]")

    try:
        # Load and process image
        input_image = Image.open(file_path)

        # Remove background
        output_image = remove(input_image)

        # Apply background replacement if needed
        if bg_color:
            # Create solid color background
            background = Image.new("RGBA", output_image.size, bg_color + (255,))
            background.paste(output_image, mask=output_image.split()[3])
            output_image = background.convert("RGB")
        elif bg_image_path:
            # Use custom background image
            bg_img = Image.open(bg_image_path).convert("RGBA")
            bg_img = bg_img.resize(output_image.size)
            bg_img.paste(output_image, mask=output_image.split()[3])
            output_image = bg_img.convert("RGB")

        # Save output
        if output_ext == ".png" and bg_option == "Transparent (PNG)":
            output_image.save(final_output, "PNG")
        else:
            if output_image.mode == "RGBA":
                output_image = output_image.convert("RGB")
            output_image.save(final_output)

        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")

    press_continue()


def remove_background_video(file_path):
    """Remove background from video frame-by-frame using AI."""
    import subprocess
    import tempfile
    import shutil

    try:
        from rembg import remove
        from PIL import Image
        import cv2
        import numpy as np
    except ImportError as e:
        console.print(f"[bold red]Error: Missing dependency - {e}[/bold red]")
        console.print("[yellow]Install with: pip install rembg onnxruntime opencv-python[/yellow]")
        press_continue()
        return

    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

    # Get video info
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        width = int(video_stream['width'])
        height = int(video_stream['height'])

        # Get frame count and fps
        if 'nb_frames' in video_stream:
            total_frames = int(video_stream['nb_frames'])
        else:
            duration = float(probe['format']['duration'])
            fps_parts = video_stream.get('r_frame_rate', '30/1').split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
            total_frames = int(duration * fps)

        fps_parts = video_stream.get('r_frame_rate', '30/1').split('/')
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])

    except Exception as e:
        console.print(f"[bold red]Error reading video: {e}[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Video: {width}x{height}, ~{total_frames} frames, {fps:.2f} FPS[/dim]")

    bg_option = questionary.select(
        "What should replace the background?",
        choices=[
            "Green Screen (Chroma Key)",
            "Solid Color",
            "Transparent (WebM)",
            "Custom Image",
            "← Back"
        ]
    ).ask()

    if bg_option == "← Back" or bg_option is None:
        return

    bg_color = None
    bg_image_path = None
    output_transparent = False

    if bg_option == "Green Screen (Chroma Key)":
        bg_color = (0, 255, 0)
    elif bg_option == "Transparent (WebM)":
        output_transparent = True
    elif bg_option == "Solid Color":
        color_choice = questionary.select(
            "Select background color:",
            choices=["White", "Black", "Blue", "Custom (Hex)"]
        ).ask()

        if not color_choice:
            return

        color_map = {"White": (255, 255, 255), "Black": (0, 0, 0), "Blue": (0, 0, 255)}
        if color_choice == "Custom (Hex)":
            hex_color = questionary.text("Enter hex color (e.g., #FF5733):").ask()
            if hex_color:
                hex_color = hex_color.lstrip('#')
                try:
                    bg_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                except ValueError:
                    bg_color = (255, 255, 255)
            else:
                bg_color = (255, 255, 255)
        else:
            bg_color = color_map.get(color_choice, (255, 255, 255))

    elif bg_option == "Custom Image":
        bg_image_path = questionary.text("Enter path to background image:").ask()
        if not bg_image_path or not os.path.exists(bg_image_path):
            console.print("[bold red]Background image not found.[/bold red]")
            press_continue()
            return

    # Output format
    if output_transparent:
        output_ext = ".webm"
        suffix = "nobg_transparent"
    else:
        output_ext = ".mp4"
        suffix = "nobg"

    output_file = f"{Path(file_path).stem}_{suffix}{output_ext}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        return

    console.print("[bold cyan]Processing video (AI background removal)...[/bold cyan]")
    console.print("[dim]First run will download the AI model (~170MB)[/dim]")
    console.print("[dim]This is a slow process - each frame is processed by AI.[/dim]")

    # Create temp directory for frames
    import tempfile
    temp_dir = tempfile.mkdtemp()
    cap = None

    try:
        # Load background image if specified
        bg_img = None
        if bg_image_path:
            bg_img = Image.open(bg_image_path).convert("RGBA")
            bg_img = bg_img.resize((width, height))

        # Open video
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            console.print("[bold red]Error: Cannot open video file.[/bold red]")
            press_continue()
            return

        frame_count = 0
        processed_frames = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Removing backgrounds...", total=total_frames)

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)

                # Remove background
                output_image = remove(pil_image)

                # Apply background replacement
                if output_transparent:
                    # Keep RGBA for transparent output
                    final_frame = output_image
                elif bg_color:
                    background = Image.new("RGBA", output_image.size, bg_color + (255,))
                    background.paste(output_image, mask=output_image.split()[3])
                    final_frame = background.convert("RGB")
                elif bg_img:
                    bg_copy = bg_img.copy()
                    bg_copy.paste(output_image, mask=output_image.split()[3])
                    final_frame = bg_copy.convert("RGB")
                else:
                    final_frame = output_image.convert("RGB")

                # Save frame
                frame_path = os.path.join(temp_dir, f"frame_{frame_count:06d}.png")
                final_frame.save(frame_path, "PNG")
                processed_frames.append(frame_path)

                frame_count += 1
                progress.update(task, advance=1)

        if frame_count == 0:
            console.print("[bold red]No frames were processed.[/bold red]")
            return

        console.print(f"[green]Processed {frame_count} frames. Reassembling video...[/green]")

        # Reassemble video with FFmpeg
        frame_pattern = os.path.join(temp_dir, "frame_%06d.png")

        from peg_this.settings import Settings
        settings = Settings()

        if output_transparent:
            # WebM with alpha channel (requires vp9 usually, not hw accel friendly always)
            # Keeping software VP9 for transparency for safety
            cmd = [
                'ffmpeg', '-y' if action_result == 'overwrite' else '-n',
                '-framerate', str(fps),
                '-i', frame_pattern,
                '-c:v', 'libvpx-vp9',
                '-pix_fmt', 'yuva420p',
                '-crf', '30',
                '-b:v', '0',
                final_output
            ]
        else:
            # MP4 (no alpha) - Use HW accel
            encoding_args = settings.get_encoder_list_args(quality="medium", crf=18)
            cmd = [
                'ffmpeg', '-y' if action_result == 'overwrite' else '-n',
                '-framerate', str(fps),
                '-i', frame_pattern,
            ]
            cmd.extend(encoding_args)
            cmd.extend([
                '-pix_fmt', 'yuv420p',
                final_output
            ])

        # Add audio if present
        if has_audio_stream(file_path):
            # We need to add audio from original file
            cmd_with_audio = [
                'ffmpeg', '-y' if action_result == 'overwrite' else '-n',
                '-framerate', str(fps),
                '-i', frame_pattern,
                '-i', file_path,
                '-map', '0:v',
                '-map', '1:a?',
            ]
            if output_transparent:
                cmd_with_audio.extend(['-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-crf', '30', '-b:v', '0'])
            else:
                cmd_with_audio.extend(encoding_args)
                cmd_with_audio.extend(['-pix_fmt', 'yuv420p'])

            cmd_with_audio.extend(['-c:a', 'copy', '-shortest', final_output])
            cmd = cmd_with_audio

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
        else:
            console.print("[bold red]Failed to create output video.[/bold red]")
            if result.stderr:
                error_lines = result.stderr.strip().split('\n')[-3:]
                console.print(f"[dim]{' '.join(error_lines)}[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
    finally:
        if cap:
            cap.release()
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        press_continue()
