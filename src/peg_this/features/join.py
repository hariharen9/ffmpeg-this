
import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command
from peg_this.utils.ui_utils import get_media_files

console = Console()


def join_videos():
    """Join multiple videos into a single file after standardizing their resolutions and sample rates."""
    console.print("[bold cyan]Select videos to join (in order). Press Enter when done.[/bold cyan]")
    
    media_files = get_media_files()
    video_files = [f for f in media_files if Path(f).suffix.lower() in [".mp4", ".mkv", ".mov", ".avi", ".webm"]]

    if len(video_files) < 2:
        console.print("[bold yellow]Not enough video files in the directory to join.[/bold yellow]")
        questionary.press_any_key_to_continue().ask()
        return

    selected_videos = questionary.checkbox("Select at least two videos to join in order:", choices=video_files).ask()

    if not selected_videos or len(selected_videos) < 2:
        console.print("[bold yellow]Joining cancelled. At least two videos must be selected.[/bold yellow]")
        return

    console.print("Videos will be joined in this order:")
    for i, video in enumerate(selected_videos):
        console.print(f"  {i+1}. {video}")

    output_file = questionary.text("Enter the output file name:", default="joined_video.mp4").ask()
    if not output_file: return

    try:
        first_video_path = os.path.abspath(selected_videos[0])
        probe = ffmpeg.probe(first_video_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        audio_info = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
        
        target_width = video_info['width']
        target_height = video_info['height']
        target_sar = video_info.get('sample_aspect_ratio', '1:1')
        target_sample_rate = audio_info['sample_rate']

    except Exception as e:
        console.print(f"[bold red]Could not probe first video for target parameters: {e}[/bold red]")
        return

    console.print(f"Standardizing all videos to: {target_width}x{target_height} resolution and {target_sample_rate} Hz audio.")

    processed_streams = []
    for video_file in selected_videos:
        stream = ffmpeg.input(os.path.abspath(video_file))
        v = (
            stream.video
            .filter('scale', w=target_width, h=target_height, force_original_aspect_ratio='decrease')
            .filter('pad', w=target_width, h=target_height, x='(ow-iw)/2', y='(oh-ih)/2')
            .filter('setsar', sar=target_sar.replace(':','/'))
            .filter('setpts', 'PTS-STARTPTS')
        )
        a = (
            stream.audio
            .filter('aresample', sample_rate=target_sample_rate)
            .filter('asetpts', 'PTS-STARTPTS')
        )
        processed_streams.append(v)
        processed_streams.append(a)

    joined = ffmpeg.concat(*processed_streams, v=1, a=1).node
    output_stream = ffmpeg.output(joined[0], joined[1], output_file, **{'c:v': 'libx264', 'crf': 23, 'c:a': 'aac', 'b:a': '192k', 'y': None})

    if run_command(output_stream, "Joining and re-encoding videos...", show_progress=True):
        console.print(f"[bold green]Successfully joined videos into {output_file}[/bold green]")
    else:
        console.print("[bold red]Failed to join videos.[/bold red]")
    
    questionary.press_any_key_to_continue().ask()
