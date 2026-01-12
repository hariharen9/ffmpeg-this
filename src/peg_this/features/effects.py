import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, check_disk_space, press_continue
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
