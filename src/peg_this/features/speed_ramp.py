import os
import tempfile
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream, get_global_encoding_args
from peg_this.utils.validation import (
    validate_input_file, check_output_file, get_video_duration,
    validate_time_input, format_duration, press_continue
)

console = Console()


def partial_speed_adjustment(file_path):
    """
    Adjust the speed of a specific section of a video.
    Logic:
    1. Split into 3 parts: Before, During, After
    2. Apply speed filters to the 'During' part
    3. Concatenate all 3 parts
    """
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration <= 0:
        console.print("[bold red]Error: Could not determine video duration.[/bold red]")
        press_continue()
        return

    console.print(f"\n[bold cyan]Partial Speed Adjustment (Speed Ramp)[/bold cyan]")
    console.print(f"[dim]Total Duration: {format_duration(duration)}[/dim]\n")

    # 1. Get Start Time
    start_time_str = questionary.text(
        "Enter start time of speed change (HH:MM:SS or seconds):",
        default="0"
    ).ask()
    if start_time_str is None:
        return

    start_time = validate_time_input(start_time_str, duration, "Start time")
    if start_time is None:
        press_continue()
        return

    # 2. Get End Time
    end_time_str = questionary.text(
        "Enter end time of speed change (HH:MM:SS or seconds):",
        default=str(duration)
    ).ask()
    if end_time_str is None:
        return

    end_time = validate_time_input(end_time_str, duration, "End time")
    if end_time is None:
        press_continue()
        return

    if end_time <= start_time:
        console.print("[bold red]Error: End time must be greater than start time.[/bold red]")
        press_continue()
        return

    # 3. Get Speed Multiplier
    speed_choice = questionary.select(
        "Select speed multiplier for this section:",
        choices=[
            "0.25x (Very Slow)",
            "0.5x (Slow)",
            "2x (Fast)",
            "4x (Very Fast)",
            "Custom"
        ],
        default="2x (Fast)"
    ).ask()

    if speed_choice is None:
        return

    if speed_choice == "Custom":
        custom_speed = questionary.text(
            "Enter speed multiplier (e.g., 1.5):",
            default="2.0"
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
        speed_factor = float(speed_choice.split('x')[0])

    # 4. Confirmation
    ramp_duration = end_time - start_time
    new_ramp_duration = ramp_duration / speed_factor
    final_duration = (duration - ramp_duration) + new_ramp_duration

    console.print(f"\n[yellow]Action Summary:[/yellow]")
    console.print(f" • Segment: [bold]{format_duration(start_time)}[/bold] to [bold]{format_duration(end_time)}[/bold]")
    console.print(f" • Speed: [bold]{speed_factor}x[/bold]")
    console.print(f" • Resulting Total Duration: ~[bold]{format_duration(final_duration)}[/bold]\n")

    if not questionary.confirm("Proceed with partial speed adjustment?", default=True).ask():
        return

    output_file = f"{Path(file_path).stem}_speed_ramp{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        return

    # 5. FFmpeg Filter Logic
    input_stream = ffmpeg.input(file_path)
    has_audio = has_audio_stream(file_path)
    
    # Video PTS factor (lower = faster)
    v_factor = 1.0 / speed_factor
    
    # Filter for Audio
    def get_audio_speed_filter(a_stream, factor):
        if factor > 2.0:
            remaining = factor
            while remaining > 2.0:
                a_stream = a_stream.filter('atempo', 2.0)
                remaining /= 2.0
            return a_stream.filter('atempo', remaining)
        elif factor < 0.5:
            remaining = factor
            while remaining < 0.5:
                a_stream = a_stream.filter('atempo', 0.5)
                remaining /= 0.5
            return a_stream.filter('atempo', remaining)
        else:
            return a_stream.filter('atempo', factor)

    # Segment 1: Before
    v1 = input_stream.video.trim(start=0, end=start_time).setpts('PTS-STARTPTS')
    if has_audio:
        a1 = input_stream.audio.filter('atrim', start=0, end=start_time).filter('asetpts', 'PTS-STARTPTS')

    # Segment 2: During (Sped up)
    v2 = input_stream.video.trim(start=start_time, end=end_time).setpts(f'{v_factor}*(PTS-STARTPTS)')
    if has_audio:
        a2 = input_stream.audio.filter('atrim', start=start_time, end=end_time).filter('asetpts', 'PTS-STARTPTS')
        a2 = get_audio_speed_filter(a2, speed_factor)

    # Segment 3: After
    v3 = input_stream.video.trim(start=end_time).setpts('PTS-STARTPTS')
    if has_audio:
        a3 = input_stream.audio.filter('atrim', start=end_time).filter('asetpts', 'PTS-STARTPTS')

    # Concatenate
    if has_audio:
        joined = ffmpeg.concat(v1, a1, v2, a2, v3, a3, v=1, a=1).node
        out = ffmpeg.output(joined[0], joined[1], final_output, **get_global_encoding_args(crf=23))
    else:
        joined = ffmpeg.concat(v1, v2, v3, v=1, a=0).node
        out = ffmpeg.output(joined[0], final_output, **get_global_encoding_args(crf=23))

    if action_result == 'overwrite':
        out = out.overwrite_output()

    if run_command(out, f"Applying speed ramp ({speed_factor}x)...", show_progress=True):
        console.print(f"\n[bold green]Success! Video saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to apply speed ramp.[/bold red]")

    press_continue()
