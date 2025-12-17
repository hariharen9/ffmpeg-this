import os
import logging

import ffmpeg
import questionary
from rich.console import Console
from rich.table import Table

from peg_this.utils.validation import validate_input_file, press_continue

console = Console()


def inspect_file(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    console.print(f"Inspecting [bold]{os.path.basename(file_path)}[/bold]...")

    try:
        info = ffmpeg.probe(file_path)
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode('utf-8') if e.stderr else "Unknown error"
        console.print("[bold red]An error occurred while inspecting the file:[/bold red]")
        console.print(f"[dim]{error_msg}[/dim]")
        logging.error(f"ffprobe error: {error_msg}")
        press_continue()
        return

    format_info = info.get('format', {})

    if not format_info:
        console.print("[bold red]Error: Could not read file format information.[/bold red]")
        press_continue()
        return

    table = Table(title=f"File Information: {os.path.basename(file_path)}", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    try:
        size_mb = float(format_info.get('size', 0)) / (1024 * 1024)
        duration_sec = float(format_info.get('duration', 0))
        bit_rate_kbps = float(format_info.get('bit_rate', 0)) / 1000
    except (ValueError, TypeError):
        size_mb = 0
        duration_sec = 0
        bit_rate_kbps = 0

    table.add_row("Size", f"{size_mb:.2f} MB")
    table.add_row("Duration", f"{duration_sec:.2f} seconds" if duration_sec > 0 else "N/A")
    table.add_row("Format", format_info.get('format_long_name', 'N/A'))
    table.add_row("Bitrate", f"{bit_rate_kbps:.0f} kb/s" if bit_rate_kbps > 0 else "N/A")
    console.print(table)

    streams = info.get('streams', [])

    for stream_type in ['video', 'audio', 'subtitle']:
        type_streams = [s for s in streams if s.get('codec_type') == stream_type]
        if type_streams:
            if stream_type == 'video':
                color = 'cyan'
            elif stream_type == 'audio':
                color = 'green'
            else:
                color = 'yellow'

            stream_table = Table(title=f"{stream_type.capitalize()} Streams", show_header=True, header_style=f"bold {color}")
            stream_table.add_column("Stream")
            stream_table.add_column("Codec")

            if stream_type == 'video':
                stream_table.add_column("Resolution")
                stream_table.add_column("Frame Rate")
            elif stream_type == 'audio':
                stream_table.add_column("Sample Rate")
                stream_table.add_column("Channels")
            else:
                stream_table.add_column("Language")

            for s in type_streams:
                if stream_type == 'video':
                    width = s.get('width', '?')
                    height = s.get('height', '?')
                    stream_table.add_row(
                        f"#{s.get('index')}",
                        s.get('codec_name', 'N/A'),
                        f"{width}x{height}",
                        s.get('r_frame_rate', 'N/A')
                    )
                elif stream_type == 'audio':
                    stream_table.add_row(
                        f"#{s.get('index')}",
                        s.get('codec_name', 'N/A'),
                        f"{s.get('sample_rate', 'N/A')} Hz",
                        str(s.get('channels', 'N/A'))
                    )
                else:
                    tags = s.get('tags', {})
                    lang = tags.get('language', 'N/A')
                    stream_table.add_row(
                        f"#{s.get('index')}",
                        s.get('codec_name', 'N/A'),
                        lang
                    )

            console.print(stream_table)

    press_continue()
