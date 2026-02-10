import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, get_global_encoding_args
from peg_this.utils.ui_utils import get_media_files
from peg_this.utils.validation import (
    check_output_file, check_has_audio_stream, warn_reencode, press_continue
)

console = Console()


def join_videos():
    console.print("[bold cyan]Select videos to join (in order).[/bold cyan]")

    media_files = get_media_files()
    video_files = [f for f in media_files if Path(f).suffix.lower() in [".mp4", ".mkv", ".mov", ".avi", ".webm"]]

    if len(video_files) < 2:
        console.print("[bold yellow]Not enough video files in the directory to join (need at least 2).[/bold yellow]")
        press_continue()
        return

    selected_videos = questionary.checkbox(
        "Select at least two videos to join in order:",
        choices=video_files
    ).ask()

    if not selected_videos or len(selected_videos) < 2:
        console.print("[bold yellow]Joining cancelled. At least two videos must be selected.[/bold yellow]")
        press_continue()
        return

    console.print("\n[cyan]Videos will be joined in this order:[/cyan]")
    for i, video in enumerate(selected_videos):
        console.print(f"  {i+1}. {video}")

    output_file = questionary.text("Enter the output file name:", default="joined_video.mp4").ask()
    if not output_file:
        return

    action_result, final_output = check_output_file(output_file, "Video file")
    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    try:
        first_video_path = os.path.abspath(selected_videos[0])
        probe = ffmpeg.probe(first_video_path)
        video_info = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)

        if not video_info:
            console.print("[bold red]Error: First video has no video stream.[/bold red]")
            press_continue()
            return

        target_width = video_info['width']
        target_height = video_info['height']
        target_sar = video_info.get('sample_aspect_ratio', '1:1')

        # Check for audio stream (optional)
        audio_info = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
        has_audio = audio_info is not None
        target_sample_rate = audio_info['sample_rate'] if audio_info else '44100'

    except Exception as e:
        console.print(f"[bold red]Could not probe first video: {e}[/bold red]")
        press_continue()
        return

    # Check if all videos have audio (if first one does)
    if has_audio:
        for video in selected_videos[1:]:
            if not check_has_audio_stream(os.path.abspath(video)):
                console.print(f"[yellow]Warning: '{video}' has no audio stream.[/yellow]")
                if not questionary.confirm("Continue anyway? (silent sections will be added)", default=True).ask():
                    return

    console.print(f"\n[dim]Standardizing to: {target_width}x{target_height} @ {target_sample_rate} Hz[/dim]")
    warn_reencode("Joining videos")

    processed_streams = []
    for video_file in selected_videos:
        abs_path = os.path.abspath(video_file)
        stream = ffmpeg.input(abs_path)

        v = (
            stream.video
            .filter('scale', w=target_width, h=target_height, force_original_aspect_ratio='decrease')
            .filter('pad', w=target_width, h=target_height, x='(ow-iw)/2', y='(oh-ih)/2')
            .filter('setsar', sar=target_sar.replace(':', '/'))
            .filter('setpts', 'PTS-STARTPTS')
        )
        processed_streams.append(v)

        if has_audio:
            if check_has_audio_stream(abs_path):
                a = (
                    stream.audio
                    .filter('aresample', sample_rate=target_sample_rate)
                    .filter('asetpts', 'PTS-STARTPTS')
                )
            else:
                # Generate silent audio for videos without audio
                a = ffmpeg.input('anullsrc', f='lavfi', t=1).filter('aresample', sample_rate=target_sample_rate)
            processed_streams.append(a)

    encoding_args = get_global_encoding_args(crf=23)

    if has_audio:
        joined = ffmpeg.concat(*processed_streams, v=1, a=1).node
        encoding_args['c:a'] = 'aac'
        encoding_args['b:a'] = '192k'
        output_stream = ffmpeg.output(
            joined[0], joined[1], final_output,
            **encoding_args
        )
    else:
        joined = ffmpeg.concat(*processed_streams, v=1, a=0).node
        output_stream = ffmpeg.output(
            joined[0], final_output,
            **encoding_args
        )

    if action_result == 'overwrite':
        output_stream = output_stream.overwrite_output()

    try:
        if run_command(output_stream, "Joining and re-encoding videos...", show_progress=True):
            console.print(f"[bold green]Successfully joined videos into {final_output}[/bold green]")
        else:
            console.print("[bold red]Failed to join videos.[/bold red]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")

    press_continue()
