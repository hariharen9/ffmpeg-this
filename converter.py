import os
import subprocess
import json
from pathlib import Path
import sys

try:
    import questionary
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
except ImportError:
    print("Required libraries not found. Please install them by running:")
    print("pip install questionary rich")
    sys.exit(1)

console = Console()


def check_ffmpeg_ffprobe():
    """Check if ffmpeg and ffprobe executables are available."""
    for tool in ["ffmpeg", "ffprobe"]:
        executable = tool + ".exe" if sys.platform == "win32" else tool
        if not any(os.path.exists(os.path.join(p, executable)) for p in os.environ["PATH"].split(os.pathsep)):
             if not os.path.exists(os.path.join(os.path.dirname(os.path.realpath(__file__)), executable)):
                console.print(f"[bold red]Error: {executable} not found.[/bold red]")
                console.print("Please make sure FFmpeg and FFprobe are in the same directory as this script, or in your system's PATH.")
                sys.exit(1)


def run_command(command, description="Processing...", show_progress=False):
    """Runs a command using subprocess, with an optional progress bar."""
    console.print(f"[bold cyan]{description}[/bold cyan]")

    if not show_progress:
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            console.print("[bold red]An error occurred:[/bold red]")
            console.print(e.stderr)
            return None
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task(description, total=100)
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8'
            )

            duration = 0
            for line in process.stdout:
                if "Duration" in line:
                    try:
                        time_str = line.split("Duration: ")[1].split(",")[0].strip()
                        h, m, s = time_str.split(':')
                        duration = int(h) * 3600 + int(m) * 60 + float(s)
                    except Exception:
                        pass
                if "time=" in line and duration > 0:
                    try:
                        time_str = line.split("time=")[1].split(" ")[0].strip()
                        h, m, s = time_str.split(':')
                        elapsed_time = int(h) * 3600 + int(m) * 60 + float(s)
                        progress.update(task, completed=(elapsed_time / duration) * 100)
                    except Exception:
                        pass

            process.wait()
            progress.update(task, completed=100)
            if process.returncode != 0:
                console.print(f"[bold red]An error occurred during processing.[/bold red]")
                return None
        return "Success"


def get_media_files():
    """Scan the current directory for media files."""
    media_extensions = [".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".wmv", ".mp3", ".flac", ".wav", ".ogg"]
    files = [f for f in os.listdir('.') if os.path.isfile(f) and Path(f).suffix.lower() in media_extensions]
    return files


def select_media_file():
    """Display a menu to select a media file."""
    media_files = get_media_files()
    if not media_files:
        console.print("[bold yellow]No media files found in this directory.[/bold yellow]")
        return None

    file = questionary.select(
        "Select a media file to process:",
        choices=media_files + [questionary.Separator(), "Back"],
        use_indicator=True
    ).ask()

    return file if file != "Back" else None


def inspect_file(file_path):
    """Show detailed information about the selected media file."""
    command = f'ffprobe -v quiet -print_format json -show_format -show_streams "{file_path}"'
    info_json = run_command(command, f"Inspecting {file_path}...")

    if not info_json:
        return

    info = json.loads(info_json)
    format_info = info.get('format', {})

    table = Table(title=f"File Information: {os.path.basename(file_path)}", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    size_bytes = int(format_info.get('size', 0))
    size_mb = size_bytes / (1024 * 1024)
    duration_sec = float(format_info.get('duration', 0))

    table.add_row("Size", f"{size_mb:.2f} MB")
    table.add_row("Duration", f"{duration_sec:.2f} seconds")
    table.add_row("Format", format_info.get('format_long_name', 'N/A'))
    table.add_row("Bitrate", f"{float(format_info.get('bit_rate', 0)) / 1000:.0f} kb/s")

    console.print(table)

    video_streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
    if video_streams:
        video_table = Table(title="Video Streams", show_header=True, header_style="bold cyan")
        video_table.add_column("Stream")
        video_table.add_column("Codec")
        video_table.add_column("Resolution")
        video_table.add_column("Frame Rate")
        for s in video_streams:
            video_table.add_row(
                f"#{s.get('index')}",
                s.get('codec_name'),
                f"{s.get('width')}x{s.get('height')}",
                s.get('r_frame_rate')
            )
        console.print(video_table)

    audio_streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'audio']
    if audio_streams:
        audio_table = Table(title="Audio Streams", show_header=True, header_style="bold green")
        audio_table.add_column("Stream")
        audio_table.add_column("Codec")
        audio_table.add_column("Sample Rate")
        audio_table.add_column("Channels")
        for s in audio_streams:
            audio_table.add_row(
                f"#{s.get('index')}",
                s.get('codec_name'),
                f"{s.get('sample_rate')} Hz",
                str(s.get('channels'))
            )
        console.print(audio_table)

    questionary.press_any_key_to_continue().ask()


def convert_lossless(file_path):
    """Convert a file to a different container without re-encoding."""
    output_format = questionary.select(
        "Select output format:",
        choices=["mp4", "mkv", "mov"],
        use_indicator=True
    ).ask()

    if not output_format: return

    output_file = f"{Path(file_path).stem}_lossless.{output_format}"
    command = f'ffmpeg -i "{file_path}" -map 0 -c copy -c:s mov_text "{output_file}"'
    run_command(command, f"Converting to {output_format}...", show_progress=True)
    console.print(f"[bold green]Successfully converted to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()

def convert_lossy(file_path):
    """Re-encode a video to a smaller file size."""
    quality = questionary.select(
        "Select quality preset (lower CRF is higher quality):",
        choices=[
            questionary.Choice("High Quality (CRF 18)", 18),
            questionary.Choice("Medium Quality (CRF 23)", 23),
            questionary.Choice("Low Quality (CRF 28)", 28)
        ],
        use_indicator=True
    ).ask()

    if not quality: return

    output_file = f"{Path(file_path).stem}_crf{quality}.mp4"
    command = f'ffmpeg -i "{file_path}" -c:v libx264 -crf {quality} -c:a copy "{output_file}"'
    run_command(command, f"Encoding with CRF {quality}...", show_progress=True)
    console.print(f"[bold green]Successfully encoded to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()

def trim_video(file_path):
    """Cut a video by specifying start and end times."""
    start_time = questionary.text("Enter start time (HH:MM:SS):").ask()
    if not start_time: return
    end_time = questionary.text("Enter end time (HH:MM:SS):").ask()
    if not end_time: return

    output_file = f"{Path(file_path).stem}_trimmed{Path(file_path).suffix}"
    command = f'ffmpeg -i "{file_path}" -ss {start_time} -to {end_time} -c copy "{output_file}"'
    run_command(command, "Trimming video...", show_progress=True)
    console.print(f"[bold green]Successfully trimmed to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()

def extract_audio(file_path):
    """Extract the audio track from a video file."""
    audio_format = questionary.select(
        "Select audio format:",
        choices=[
            questionary.Choice("MP3 (lossy)", {"codec": "libmp3lame -q:a 2", "ext": "mp3"}),
            questionary.Choice("FLAC (lossless)", {"codec": "flac", "ext": "flac"}),
            questionary.Choice("WAV (uncompressed)", {"codec": "pcm_s16le", "ext": "wav"})
        ],
        use_indicator=True
    ).ask()

    if not audio_format: return

    output_file = f"{Path(file_path).stem}_audio.{audio_format['ext']}"
    command = f'ffmpeg -i "{file_path}" -vn -c:a {audio_format["codec"]} "{output_file}"'
    run_command(command, f"Extracting audio to {audio_format['ext'].upper()}...", show_progress=True)
    console.print(f"[bold green]Successfully extracted audio to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()

def remove_audio(file_path):
    """Create a silent version of a video."""
    output_file = f"{Path(file_path).stem}_no_audio{Path(file_path).suffix}"
    command = f'ffmpeg -i "{file_path}" -c:v copy -an "{output_file}"'
    run_command(command, "Removing audio track...", show_progress=True)
    console.print(f"[bold green]Successfully removed audio, saved to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()

def batch_convert():
    """Convert all video files in the directory to a specific format."""
    output_format = questionary.select(
        "Select output format for the batch conversion:",
        choices=["mp4", "mkv", "mov"],
        use_indicator=True
    ).ask()

    if not output_format: return

    confirm = questionary.confirm(
        f"This will convert ALL video files in the current directory to .{output_format}. Are you sure?",
        default=False
    ).ask()

    if not confirm:
        console.print("[bold yellow]Batch conversion cancelled.[/bold yellow]")
        return

    video_extensions = [".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".wmv"]
    files_to_convert = [f for f in os.listdir('.') if os.path.isfile(f) and Path(f).suffix.lower() in video_extensions]

    for file in files_to_convert:
        output_file = f"{Path(file).stem}_batch.{output_format}"
        command = f'ffmpeg -i "{file}" -map 0 -c copy -c:s mov_text "{output_file}"'
        run_command(command, f"Converting {file}...", show_progress=True)
        console.print(f"  -> Saved as {output_file}")

    console.print("\n[bold green]Batch conversion finished.[/bold green]")
    questionary.press_any_key_to_continue().ask()

def action_menu(file_path):
    """Display the menu of actions for a selected file."""
    while True:
        console.rule(f"[bold]Actions for: {file_path}[/bold]")
        action = questionary.select(
            "Choose an action:",
            choices=[
                "Inspect File Details",
                "Convert (Lossless)",
                "Convert (Smaller File Size)",
                "Trim Video",
                "Extract Audio",
                "Remove Audio",
                questionary.Separator(),
                "Back to File List"
            ],
            use_indicator=True
        ).ask()

        if action is None or action == "Back to File List":
            break

        actions = {
            "Inspect File Details": inspect_file,
            "Convert (Lossless)": convert_lossless,
            "Convert (Smaller File Size)": convert_lossy,
            "Trim Video": trim_video,
            "Extract Audio": extract_audio,
            "Remove Audio": remove_audio,
        }
        actions[action](file_path)

def main_menu():
    """Display the main menu."""
    check_ffmpeg_ffprobe()
    while True:
        console.rule("[bold magenta]Enhanced Media Converter[/bold magenta]")
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Select a Media File to Process",
                "Batch Convert All Videos to a Format",
                "Exit"
            ],
            use_indicator=True
        ).ask()

        if choice is None or choice == "Exit":
            console.print("[bold]Goodbye![/bold]")
            break
        elif choice == "Select a Media File to Process":
            selected_file = select_media_file()
            if selected_file:
                action_menu(selected_file)
        elif choice == "Batch Convert All Videos to a Format":
            batch_convert()


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[bold]Operation cancelled by user. Goodbye![/bold]")
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
