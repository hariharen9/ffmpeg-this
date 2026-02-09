import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, get_video_duration,
    format_duration, press_continue
)

console = Console()


def change_speed(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration > 0:
        console.print(f"[dim]Current duration: {format_duration(duration)}[/dim]")

    speed = questionary.select(
        "Select speed:",
        choices=[
            "0.25x (Very Slow)",
            "0.5x (Slow)",
            "0.75x (Slightly Slow)",
            "1.5x (Slightly Fast)",
            "2x (Fast)",
            "4x (Very Fast)",
            "Custom",
            "← Back"
        ]
    ).ask()

    if speed == "← Back" or speed is None:
        return

    if speed == "Custom":
        custom_speed = questionary.text(
            "Enter speed multiplier (e.g., 1.5 for 1.5x faster):",
            default="1.5"
        ).ask()
        if not custom_speed:
            return
        try:
            speed_factor = float(custom_speed)
            if speed_factor <= 0:
                console.print("[bold red]Speed must be positive.[/bold red]")
                press_continue()
                return
        except ValueError:
            console.print("[bold red]Invalid speed value.[/bold red]")
            press_continue()
            return
    else:
        speed_factor = float(speed.split('x')[0])

    new_duration = duration / speed_factor
    console.print(f"[dim]New duration will be: {format_duration(new_duration)}[/dim]")

    if speed_factor > 1:
        suffix = f"_{speed_factor}x_fast"
    else:
        suffix = f"_{speed_factor}x_slow"

    output_file = f"{Path(file_path).stem}{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # Video speed: setpts filter (lower = faster)
    video_tempo = 1 / speed_factor

    input_stream = ffmpeg.input(file_path)
    video = input_stream.video.filter('setpts', f'{video_tempo}*PTS')

    if has_audio_stream(file_path):
        # Audio speed: atempo filter (only supports 0.5 to 2.0)
        # Chain multiple atempo filters for larger changes
        audio = input_stream.audio

        if speed_factor > 2.0:
            # Chain atempo filters for speeds > 2x
            remaining = speed_factor
            while remaining > 2.0:
                audio = audio.filter('atempo', 2.0)
                remaining /= 2.0
            audio = audio.filter('atempo', remaining)
        elif speed_factor < 0.5:
            # Chain atempo filters for speeds < 0.5x
            remaining = speed_factor
            while remaining < 0.5:
                audio = audio.filter('atempo', 0.5)
                remaining /= 0.5
            audio = audio.filter('atempo', remaining)
        else:
            audio = audio.filter('atempo', speed_factor)

        stream = ffmpeg.output(video, audio, final_output, **{'c:v': 'libx264', 'crf': 23})
    else:
        stream = ffmpeg.output(video, final_output, **{'c:v': 'libx264', 'crf': 23})

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Changing speed to {speed_factor}x...", show_progress=True):
        console.print(f"[bold green]Saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]Speed change failed.[/bold red]")

    press_continue()


def smooth_slow_motion(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration > 0:
        console.print(f"[dim]Current duration: {format_duration(duration)}[/dim]")

    speed = questionary.select(
        "Select speed (slower = smoother):",
        choices=[
            "0.5x (Slow)",
            "0.25x (Very Slow)",
            "0.125x (Super Slow)",
            "Custom",
            "← Back"
        ]
    ).ask()

    if speed == "← Back" or speed is None:
        return

    if speed == "Custom":
        custom_speed = questionary.text(
            "Enter speed multiplier (e.g., 0.1 for 10x slower):",
            default="0.5"
        ).ask()
        if not custom_speed:
            return
        try:
            speed_factor = float(custom_speed)
            if speed_factor <= 0 or speed_factor >= 1.0:
                console.print("[bold red]For slow motion, speed must be between 0 and 1.[/bold red]")
                press_continue()
                return
        except ValueError:
            console.print("[bold red]Invalid speed value.[/bold red]")
            press_continue()
            return
    else:
        speed_factor = float(speed.split('x')[0])

    target_fps_choice = questionary.select(
        "Target FPS (higher = smoother playback):",
        choices=[
            "60 fps (Recommended)",
            "30 fps",
            "Keep Original",
            "Custom"
        ]
    ).ask()

    if target_fps_choice is None:
        return

    target_fps_val = None
    if "60" in target_fps_choice:
        target_fps_val = 60
    elif "30" in target_fps_choice:
        target_fps_val = 30
    elif "Custom" in target_fps_choice:
        custom_fps = questionary.text("Enter target FPS:", default="60").ask()
        if custom_fps:
            try:
                target_fps_val = int(custom_fps)
            except ValueError:
                console.print("[bold red]Invalid FPS value. Defaulting to 60.[/bold red]")
                target_fps_val = 60

    # If "Keep Original" or fallback needed, we need to probe
    if target_fps_choice == "Keep Original":
        try:
            probe = ffmpeg.probe(file_path, select_streams='v')
            r_frame_rate = probe['streams'][0]['r_frame_rate']
            num, den = map(int, r_frame_rate.split('/'))
            target_fps_val = num / den if den != 0 else 30
        except Exception:
            target_fps_val = 30  # Safe fallback

    new_duration = duration / speed_factor
    console.print(f"[dim]New duration will be: {format_duration(new_duration)}[/dim]")

    console.print("\n[bold yellow]⚠️  WARNING: Optical Flow is computationally expensive![/bold yellow]")
    console.print(f"[dim]This uses the 'minterpolate' filter with motion compensation.[/dim]")
    console.print(f"[dim]Render time can be 10-50x the video duration depending on CPU.[/dim]")
    if not questionary.confirm("Continue?", default=True).ask():
        return

    suffix = f"_opticalflow_{speed_factor}x"
    output_file = f"{Path(file_path).stem}{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # Video speed: setpts filter (lower = faster, higher = slower)
    video_tempo = 1 / speed_factor

    input_stream = ffmpeg.input(file_path)

    # Construct minterpolate options
    # mi_mode=mci: Motion Compensated Interpolation
    # mc_mode=aobmc: Adaptive Overlapped Block Motion Compensation (higher quality)
    # me_mode=bidir: Bidirectional motion estimation
    # vsbmc=1: Variable-size block motion compensation
    minterpolate_kwargs = {
        'mi_mode': 'mci',
        'mc_mode': 'aobmc',
        'me_mode': 'bidir',
        'vsbmc': 1
    }
    if target_fps_val:
        minterpolate_kwargs['fps'] = target_fps_val

    video = input_stream.video.filter('setpts', f'{video_tempo}*PTS').filter('minterpolate', **minterpolate_kwargs)

    if has_audio_stream(file_path):
        audio = input_stream.audio
        # Audio speed logic (reuse)
        if speed_factor < 0.5:
            remaining = speed_factor
            while remaining < 0.5:
                audio = audio.filter('atempo', 0.5)
                remaining /= 0.5
            audio = audio.filter('atempo', remaining)
        else:
            audio = audio.filter('atempo', speed_factor)

        stream = ffmpeg.output(video, audio, final_output, **{'c:v': 'libx264', 'crf': 23})
    else:
        stream = ffmpeg.output(video, final_output, **{'c:v': 'libx264', 'crf': 23})

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Generating smooth slow motion ({speed_factor}x)...", show_progress=True):
        console.print(f"[bold green]Saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]Smooth slow motion failed.[/bold red]")

    press_continue()


def change_fps(file_path):
    """Change video frame rate with optional smooth interpolation."""
    if not validate_input_file(file_path):
        press_continue()
        return

    # Get current FPS
    try:
        probe = ffmpeg.probe(file_path, select_streams='v')
        r_frame_rate = probe['streams'][0]['r_frame_rate']
        num, den = map(int, r_frame_rate.split('/'))
        current_fps = num / den if den != 0 else 30
        console.print(f"[dim]Current FPS: {current_fps:.2f}[/dim]")
    except Exception:
        current_fps = 30
        console.print("[dim]Could not detect current FPS[/dim]")

    # FPS presets with descriptions
    fps_choice = questionary.select(
        "Select target frame rate:",
        choices=[
            "24 fps (Cinema/Film)",
            "25 fps (PAL/Europe TV)",
            "30 fps (NTSC/Web Standard)",
            "48 fps (High Frame Rate Cinema)",
            "60 fps (Smooth/Gaming)",
            "120 fps (Super Smooth)",
            "Custom",
            "← Back"
        ]
    ).ask()

    if fps_choice == "← Back" or fps_choice is None:
        return

    if fps_choice == "Custom":
        custom_fps = questionary.text(
            "Enter target FPS:",
            default="60"
        ).ask()
        if not custom_fps:
            return
        try:
            target_fps = float(custom_fps)
            if target_fps <= 0 or target_fps > 240:
                console.print("[bold red]FPS must be between 1 and 240.[/bold red]")
                press_continue()
                return
        except ValueError:
            console.print("[bold red]Invalid FPS value.[/bold red]")
            press_continue()
            return
    else:
        target_fps = int(fps_choice.split(" ")[0])

    # Check if upscaling FPS (needs interpolation for smooth result)
    use_interpolation = False
    if target_fps > current_fps:
        console.print(f"\n[yellow]Target FPS ({target_fps}) is higher than source ({current_fps:.0f}).[/yellow]")
        console.print("[dim]Without interpolation, frames will be duplicated (choppy).[/dim]")
        console.print("[dim]With optical flow, new frames are generated (smooth but slow).[/dim]")

        interp_choice = questionary.select(
            "How should missing frames be handled?",
            choices=[
                "Duplicate frames (Fast, may look choppy)",
                "Optical Flow interpolation (Slow, smooth result)",
                "← Back"
            ]
        ).ask()

        if interp_choice == "← Back" or interp_choice is None:
            return

        use_interpolation = "Optical Flow" in interp_choice

        if use_interpolation:
            console.print("\n[bold yellow]⚠️  Optical Flow is computationally expensive![/bold yellow]")
            console.print("[dim]Render time can be 10-50x the video duration.[/dim]")
            if not questionary.confirm("Continue?", default=True).ask():
                return

    # Output file
    suffix = f"_{int(target_fps)}fps"
    if use_interpolation:
        suffix += "_smooth"
    output_file = f"{Path(file_path).stem}{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)

    if use_interpolation:
        # Use minterpolate for smooth frame generation
        minterpolate_kwargs = {
            'fps': target_fps,
            'mi_mode': 'mci',
            'mc_mode': 'aobmc',
            'me_mode': 'bidir',
            'vsbmc': 1
        }
        video = input_stream.video.filter('minterpolate', **minterpolate_kwargs)
    else:
        # Simple FPS change (duplicate or drop frames)
        video = input_stream.video.filter('fps', fps=target_fps)

    # Keep audio unchanged
    if has_audio_stream(file_path):
        audio = input_stream.audio
        stream = ffmpeg.output(video, audio, final_output, **{'c:v': 'libx264', 'crf': 23, 'c:a': 'aac'})
    else:
        stream = ffmpeg.output(video, final_output, **{'c:v': 'libx264', 'crf': 23})

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    method = "optical flow" if use_interpolation else "frame adjustment"
    if run_command(stream, f"Changing FPS to {target_fps} ({method})...", show_progress=True):
        console.print(f"[bold green]Saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]FPS change failed.[/bold red]")

    press_continue()


def reverse_video(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration > 60:
        console.print(f"[yellow]Warning: This is a {format_duration(duration)} video.[/yellow]")
        console.print("[dim]Reversing long videos requires loading into memory and may be slow.[/dim]")
        if not questionary.confirm("Continue?", default=False).ask():
            return

    output_file = f"{Path(file_path).stem}_reversed{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)
    video = input_stream.video.filter('reverse')

    if has_audio_stream(file_path):
        audio = input_stream.audio.filter('areverse')
        stream = ffmpeg.output(video, audio, final_output, **{'c:v': 'libx264', 'crf': 23})
    else:
        stream = ffmpeg.output(video, final_output, **{'c:v': 'libx264', 'crf': 23})

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Reversing video...", show_progress=True):
        console.print(f"[bold green]Saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]Reverse failed.[/bold red]")

    press_continue()
