
import os
import logging

import ffmpeg
import questionary
from rich.console import Console
from rich.table import Table

console = Console()


def inspect_file(file_path):
    """Show detailed information about the selected media file using ffprobe."""
    console.print(f"Inspecting {os.path.basename(file_path)}...")
    try:
        info = ffmpeg.probe(file_path)
    except ffmpeg.Error as e:
        console.print("[bold red]An error occurred while inspecting the file:[/bold red]")
        console.print(e.stderr.decode('utf-8'))
        logging.error(f"ffprobe error:{e.stderr.decode('utf-8')}")
        questionary.press_any_key_to_continue().ask()
        return

    format_info = info.get('format', {})
    table = Table(title=f"File Information: {os.path.basename(file_path)}", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    size_mb = float(format_info.get('size', 0)) / (1024 * 1024)
    duration_sec = float(format_info.get('duration', 0))
    bit_rate_kbps = float(format_info.get('bit_rate', 0)) / 1000

    table.add_row("Size", f"{size_mb:.2f} MB")
    table.add_row("Duration", f"{duration_sec:.2f} seconds")
    table.add_row("Format", format_info.get('format_long_name', 'N/A'))
    table.add_row("Bitrate", f"{bit_rate_kbps:.0f} kb/s")
    console.print(table)

    for stream_type in ['video', 'audio']:
        streams = [s for s in info.get('streams', []) if s.get('codec_type') == stream_type]
        if streams:
            stream_table = Table(title=f"{stream_type.capitalize()} Streams", show_header=True, header_style=f"bold {'cyan' if stream_type == 'video' else 'green'}")
            stream_table.add_column("Stream")
            stream_table.add_column("Codec")
            if stream_type == 'video':
                stream_table.add_column("Resolution")
                stream_table.add_column("Frame Rate")
            else:
                stream_table.add_column("Sample Rate")
                stream_table.add_column("Channels")
            
            for s in streams:
                if stream_type == 'video':
                    stream_table.add_row(f"#{s.get('index')}", s.get('codec_name'), f"{s.get('width')}x{s.get('height')}", s.get('r_frame_rate'))
                else:
                    stream_table.add_row(f"#{s.get('index')}", s.get('codec_name'), f"{s.get('sample_rate')} Hz", str(s.get('channels')))
            console.print(stream_table)

    questionary.press_any_key_to_continue().ask()
