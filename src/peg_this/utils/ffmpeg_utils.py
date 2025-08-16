
import subprocess
import logging
import sys

import ffmpeg
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

console = Console()


def check_ffmpeg_ffprobe():
    """
    Checks if ffmpeg and ffprobe executables are available in the system's PATH.
    ffmpeg-python requires this.
    """
    try:
        # The library does this internally, but we can provide a clearer error message.
        subprocess.check_call(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.check_call(['ffprobe', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        console.print("[bold red]Error: ffmpeg and ffprobe not found.[/bold red]")
        if sys.platform == "win32":
            console.print("You can install it using Chocolatey: [bold]choco install ffmpeg[/bold]")
            console.print("Or Scoop: [bold]scoop install ffmpeg[/bold]")
        elif sys.platform == "darwin":
            console.print("You can install it using Homebrew: [bold]brew install ffmpeg[/bold]")
        else:
            console.print("You can install it using your system's package manager, e.g., [bold]sudo apt update && sudo apt install ffmpeg[/bold] on Debian/Ubuntu.")
        console.print("Please ensure its location is in your system's PATH.")
        sys.exit(1)


def run_command(stream_spec, description="Processing...", show_progress=False):
    """
    Runs an ffmpeg command using ffmpeg-python.
    - For simple commands, it runs directly.
    - For commands with a progress bar, it generates the ffmpeg arguments,
      runs them as a subprocess, and parses stderr to show progress,
      mimicking the logic from the original script for accuracy.
    """
    console.print(f"[bold cyan]{description}[/bold cyan]")
    
    # Get the full command arguments from the ffmpeg-python stream object
    args = stream_spec.get_args()
    full_command = ['ffmpeg'] + args
    logging.info(f"Executing command: {' '.join(full_command)}")

    if not show_progress:
        try:
            # Use ffmpeg.run() for simple, non-progress tasks. It's cleaner.
            out, err = ffmpeg.run(stream_spec, capture_stdout=True, capture_stderr=True, quiet=True)
            logging.info("Command successful (no progress bar).")
            return out.decode('utf-8')
        except ffmpeg.Error as e:
            error_message = e.stderr.decode('utf-8')
            console.print("[bold red]An error occurred:[/bold red]")
            console.print(error_message)
            logging.error(f"ffmpeg error:{error_message}")
            return None
    else:
        # For the progress bar, we must run ffmpeg as a subprocess and parse stderr.
        duration = 0
        try:
            # Find the primary input file from the command arguments to probe it.
            input_file_path = None
            for i, arg in enumerate(full_command):
                if arg == '-i' and i + 1 < len(full_command):
                    # This is a robust way to find the first input file.
                    input_file_path = full_command[i+1]
                    break
            
            if input_file_path:
                probe_info = ffmpeg.probe(input_file_path)
                duration = float(probe_info['format']['duration'])
            else:
                logging.warning("Could not find input file in command to determine duration for progress bar.")

        except (ffmpeg.Error, KeyError) as e:
            console.print(f"[bold yellow]Warning: Could not determine video duration for progress bar.[/bold yellow]")
            logging.warning(f"Could not probe for duration: {e}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task(description, total=100)
            
            # Run the command as a subprocess to capture stderr in real-time
            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8'
            )

            for line in process.stderr:
                logging.debug(f"ffmpeg stderr: {line.strip()}")
                if "time=" in line and duration > 0:
                    try:
                        time_str = line.split("time=")[1].split(" ")[0].strip()
                        h, m, s_parts = time_str.split(':')
                        s = float(s_parts)
                        elapsed_time = int(h) * 3600 + int(m) * 60 + s
                        percent_complete = (elapsed_time / duration) * 100
                        progress.update(task, completed=min(percent_complete, 100))
                    except Exception:
                        pass # Ignore any parsing errors

            process.wait()
            progress.update(task, completed=100)
            
            if process.returncode != 0:
                # The error was already logged line-by-line, but we can add a final message.
                log_file = logging.getLogger().handlers[0].baseFilename
                console.print(f"[bold red]An error occurred during processing. Check {log_file} for details.[/bold red]")
                return None
        
        logging.info("Command successful (with progress bar).")
        return "Success"


def has_audio_stream(file_path):
    """Check if the media file has an audio stream."""
    try:
        probe = ffmpeg.probe(file_path, select_streams='a')
        return 'streams' in probe and len(probe['streams']) > 0
    except ffmpeg.Error:
        return False
