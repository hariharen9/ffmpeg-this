import os
import tempfile
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command
from peg_this.utils.validation import (
    validate_input_file, check_output_file, get_video_duration,
    validate_time_input, format_duration, press_continue
)

console = Console()


def chop_middle(file_path):
    """
    Losslessly remove a middle section of a video.
    Logic: 
    1. Cut Part A (Start to ChopStart)
    2. Cut Part B (ChopEnd to End)
    3. Concat Part A and Part B using concat demuxer (lossless)
    """
    if not validate_input_file(file_path):
        press_continue()
        return

    duration = get_video_duration(file_path)
    if duration <= 0:
        console.print("[bold red]Error: Could not determine video duration.[/bold red]")
        press_continue()
        return

    console.print(f"\n[bold cyan]Lossless Chop Middle[/bold cyan]")
    console.print(f"[dim]Total Duration: {format_duration(duration)}[/dim]\n")

    # 1. Get Chop Start
    chop_start_str = questionary.text(
        "Enter start of section to REMOVE (HH:MM:SS or seconds):",
        instruction="Example: 00:00:30 to start removing at 30 seconds"
    ).ask()
    if not chop_start_str:
        return

    chop_start = validate_time_input(chop_start_str, duration, "Chop start")
    if chop_start is None:
        press_continue()
        return

    # 2. Get Chop End
    chop_end_str = questionary.text(
        "Enter end of section to REMOVE (HH:MM:SS or seconds):",
        instruction=f"Must be between {format_duration(chop_start)} and {format_duration(duration)}"
    ).ask()
    if not chop_end_str:
        return

    chop_end = validate_time_input(chop_end_str, duration, "Chop end")
    if chop_end is None:
        press_continue()
        return

    if chop_end <= chop_start:
        console.print("[bold red]Error: Chop end must be greater than chop start.[/bold red]")
        press_continue()
        return

    # 3. Confirmation and Output Path
    removed_duration = chop_end - chop_start
    final_duration = duration - removed_duration
    
    console.print(f"\n[yellow]Action Summary:[/yellow]")
    console.print(f" • Removing: [bold]{format_duration(removed_duration)}[/bold] in the middle")
    console.print(f" • Resulting Duration: [bold]{format_duration(final_duration)}[/bold]")
    console.print(f" • Mode: [bold green]Lossless (Stream Copy)[/bold green]")
    console.print(f"[dim italic]Note: Cuts are snapped to the nearest keyframe for lossless processing.[/dim italic]\n")

    if not questionary.confirm("Proceed with lossless chop?", default=True).ask():
        return

    output_file = f"{Path(file_path).stem}_chopped{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # 4. Execution logic using temp files and concat demuxer
    with tempfile.TemporaryDirectory() as temp_dir:
        suffix = Path(file_path).suffix
        part1_path = os.path.join(temp_dir, f"part1{suffix}")
        part2_path = os.path.join(temp_dir, f"part2{suffix}")
        concat_list_path = os.path.join(temp_dir, "concat.txt")

        try:
            # Segment 1: 0 to chop_start
            console.print("[cyan]Extracting first segment...[/cyan]")
            (
                ffmpeg
                .input(file_path)
                .output(part1_path, t=chop_start, c='copy', map=0, loglevel="error")
                .overwrite_output()
                .run()
            )

            # Segment 2: chop_end to end
            console.print("[cyan]Extracting second segment...[/cyan]")
            (
                ffmpeg
                .input(file_path)
                .output(part2_path, ss=chop_end, c='copy', map=0, loglevel="error")
                .overwrite_output()
                .run()
            )

            # Create concat list
            with open(concat_list_path, "w", encoding="utf-8") as f:
                # Use forward slashes for ffmpeg path compatibility
                p1 = part1_path.replace("\\", "/")
                p2 = part2_path.replace("\\", "/")
                f.write(f"file '{p1}'\n")
                f.write(f"file '{p2}'\n")

            # Final Concat
            console.print("[cyan]Joining segments losslessly...[/cyan]")
            
            # We use ffmpeg.input('concat', ...) for the demuxer
            # Note: safe=0 is needed because we are using absolute paths in the temp dir
            stream = ffmpeg.input(concat_list_path, f='concat', safe=0).output(final_output, c='copy', map=0)
            
            if action_result == 'overwrite':
                stream = stream.overwrite_output()

            if run_command(stream, "Finalizing chopped video..."):
                console.print(f"\n[bold green]Success! Chopped video saved to: {final_output}[/bold green]")
            else:
                console.print("[bold red]Failed to join segments.[/bold red]")

        except ffmpeg.Error as e:
            console.print(f"[bold red]FFmpeg Error:[/bold red] {e.stderr.decode() if e.stderr else str(e)}")
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")

    press_continue()
