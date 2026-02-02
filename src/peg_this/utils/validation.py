import os
import re
import shutil
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

console = Console()


def check_file_exists(file_path):
    if not os.path.exists(file_path):
        console.print("[bold red]Error: File not found.[/bold red]")
        return False
    return True


def check_file_readable(file_path):
    if not os.access(file_path, os.R_OK):
        console.print("[bold red]Error: Cannot read file. Check permissions.[/bold red]")
        return False
    return True


def check_write_permission(directory):
    if not os.access(directory, os.W_OK):
        console.print("[bold red]Error: Cannot write to this location. Check permissions.[/bold red]")
        return False
    return True


def validate_input_file(file_path):
    if not check_file_exists(file_path):
        return False
    if not check_file_readable(file_path):
        return False
    return True


def check_output_file(output_path, file_type="file"):
    if not os.path.exists(output_path):
        return 'proceed', output_path

    console.print(f"[yellow]Warning: {file_type} already exists:[/yellow]")
    console.print(f"[dim]{output_path}[/dim]")

    choice = questionary.select(
        "What would you like to do?",
        choices=["Overwrite existing file", "Save with a new name", "Cancel operation"]
    ).ask()

    if not choice or "Cancel" in choice:
        return 'cancel', None
    elif "Overwrite" in choice:
        return 'overwrite', output_path
    else:
        path = Path(output_path)
        counter = 1
        while True:
            new_name = f"{path.stem}_{counter}{path.suffix}"
            new_path = path.with_name(new_name)
            if not os.path.exists(new_path):
                console.print(f"[cyan]Will save as: {new_path.name}[/cyan]")
                return 'rename', str(new_path)
            counter += 1


def check_disk_space(file_path, multiplier=2):
    try:
        input_size = os.path.getsize(file_path)
        required_space = input_size * multiplier
        total, used, free = shutil.disk_usage(Path(file_path).parent)
        if free < required_space:
            free_gb = free / (1024**3)
            required_gb = required_space / (1024**3)
            console.print(f"[yellow]Warning: Low disk space![/yellow]")
            console.print(f"[dim]Available: {free_gb:.1f} GB, Estimated needed: {required_gb:.1f} GB[/dim]")
            if not questionary.confirm("Continue anyway?", default=False).ask():
                return False
        return True
    except Exception:
        return True


def get_video_duration(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        return float(probe['format'].get('duration', 0))
    except Exception:
        return 0


def format_duration(seconds):
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def parse_time_to_seconds(time_str):
    time_str = time_str.strip()

    # Already in seconds (numeric)
    if re.match(r'^\d+(\.\d+)?$', time_str):
        return float(time_str)

    # HH:MM:SS or MM:SS format
    if re.match(r'^\d{1,2}:\d{2}(:\d{2})?(\.\d+)?$', time_str):
        parts = time_str.split(':')
        if len(parts) == 2:
            mins, secs = parts
            return int(mins) * 60 + float(secs)
        elif len(parts) == 3:
            hours, mins, secs = parts
            return int(hours) * 3600 + int(mins) * 60 + float(secs)

    return None


def validate_time_input(time_str, max_duration=None, field_name="Time"):
    seconds = parse_time_to_seconds(time_str)

    if seconds is None:
        console.print(f"[bold red]Invalid {field_name.lower()} format. Use HH:MM:SS, MM:SS, or seconds.[/bold red]")
        return None

    if seconds < 0:
        console.print(f"[bold red]{field_name} cannot be negative.[/bold red]")
        return None

    if max_duration and seconds > max_duration:
        console.print(f"[bold red]{field_name} ({format_duration(seconds)}) exceeds video duration ({format_duration(max_duration)}).[/bold red]")
        return None

    return seconds


def validate_time_range(start_str, end_str, duration):
    start = validate_time_input(start_str, duration, "Start time")
    if start is None:
        return None, None

    end = validate_time_input(end_str, duration, "End time")
    if end is None:
        return None, None

    if end <= start:
        console.print("[bold red]End time must be greater than start time.[/bold red]")
        return None, None

    clip_duration = end - start
    console.print(f"[dim]Clip duration: {format_duration(clip_duration)}[/dim]")

    return start, end


def check_has_video_stream(file_path):
    try:
        probe = ffmpeg.probe(file_path, select_streams='v')
        return len(probe.get('streams', [])) > 0
    except Exception:
        return False


def check_has_audio_stream(file_path):
    try:
        probe = ffmpeg.probe(file_path, select_streams='a')
        return len(probe.get('streams', [])) > 0
    except Exception:
        return False


def warn_long_operation(duration, threshold=300, operation="This operation"):
    if duration > threshold:
        console.print(f"[yellow]Note: {operation} may take a while for this {format_duration(duration)} video.[/yellow]")
        if not questionary.confirm("Continue?", default=True).ask():
            return False
    return True


def warn_reencode(operation="This operation"):
    console.print(f"[dim]{operation} requires re-encoding and may take a while...[/dim]")


def handle_keyboard_interrupt():
    console.print("\n[yellow]Operation cancelled by user.[/yellow]")


def generate_output_path(input_path, suffix, new_extension=None):
    p = Path(input_path)
    ext = new_extension if new_extension else p.suffix
    return str(p.with_name(f"{p.stem}_{suffix}{ext}"))


def get_file_size_mb(file_path):
    try:
        size = os.path.getsize(file_path)
        return size / (1024 * 1024)
    except Exception:
        return 0


def validate_positive_integer(value, field_name="Value"):
    try:
        num = int(value)
        if num <= 0 and num != -1:  # -1 is valid for "auto" in some contexts
            console.print(f"[bold red]{field_name} must be a positive number.[/bold red]")
            return None
        return num
    except ValueError:
        console.print(f"[bold red]{field_name} must be a valid number.[/bold red]")
        return None


def confirm_operation(message, default=True):
    return questionary.confirm(message, default=default).ask()


def press_continue():
    questionary.press_any_key_to_continue().ask()
