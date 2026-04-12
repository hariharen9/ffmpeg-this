import subprocess
import logging
import sys
from collections import deque

import ffmpeg
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from peg_this.settings import Settings

console = Console()


def get_global_encoding_args(quality="medium", crf=23):
    """
    Helper to get standardized encoding arguments from global settings.
    Proxies to Settings.get_encoding_args().
    """
    return Settings().get_encoding_args(quality, crf)


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
      runs them as a subprocess, and parses stderr to show progress.
    Returns True on success, False on failure.
    """
    console.print(f"[bold cyan]{description}[/bold cyan]")
    
    args = stream_spec.get_args()
    full_command = ['ffmpeg'] + args
    logging.info(f"Executing command: {' '.join(full_command)}")

    if not show_progress:
        try:
            # Use ffmpeg.run() for simple, non-progress tasks. It's cleaner.
            ffmpeg.run(stream_spec, capture_stdout=True, capture_stderr=True, quiet=True)
            logging.info("Command successful (no progress bar).")
            return True
        except ffmpeg.Error as e:
            error_message = e.stderr.decode('utf-8')
            console.print("[bold red]An error occurred:[/bold red]")
            console.print(error_message)
            logging.error(f"ffmpeg error:{error_message}")
            return False
    else:
        # For the progress bar, we must run ffmpeg as a subprocess and parse stderr.
        duration = 0
        try:
            input_file_path = None
            for i, arg in enumerate(full_command):
                if arg == '-i' and i + 1 < len(full_command):
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
            
            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8'
            )
            
            # Capture the last few lines of stderr
            stderr_buffer = deque(maxlen=15)

            for line in process.stderr:
                stderr_buffer.append(line)
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
                        pass

            process.wait()
            progress.update(task, completed=100)
            
            if process.returncode != 0:
                log_file = logging.getLogger().handlers[0].baseFilename
                console.print("[bold red]An error occurred:[/bold red]")
                console.print("".join(stderr_buffer))
                console.print(f"Full log: {log_file}")
                return False
        
        logging.info("Command successful (with progress bar).")
        return True


def run_command_list(cmd, description="Processing...", show_progress=False, input_file=None):
    """
    Run a raw FFmpeg command list with the same progress/error UX as run_command().

    Use this when ffmpeg-python stream objects can't express the command
    (e.g. concat demuxer, multi-pass, complex filter_complex strings, -map flags).

    Args:
        cmd:           Full command as a list, e.g. ['ffmpeg', '-y', '-i', ...].
        description:   Label shown in terminal during execution.
        show_progress: If True, parse stderr for time= and show a progress bar.
        input_file:    Path to probe for total duration (for progress %).
                       If None, tries to auto-detect from the -i flag in cmd.

    Returns:
        True on success, False on failure.
    """
    console.print(f"[bold cyan]{description}[/bold cyan]")
    logging.info(f"Executing command: {' '.join(cmd)}")

    if not show_progress:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
            )
            if result.returncode == 0:
                logging.info("Command successful (no progress bar).")
                return True
            else:
                console.print("[bold red]An error occurred:[/bold red]")
                if result.stderr:
                    # Show last 500 chars of stderr for context
                    console.print(f"[dim]{result.stderr[-500:]}[/dim]")
                logging.error(f"ffmpeg error: {result.stderr}")
                return False
        except Exception as e:
            console.print(f"[bold red]Failed to execute command: {e}[/bold red]")
            logging.error(f"Command execution failed: {e}")
            return False

    # --- Progress bar mode ---
    duration = 0
    # Determine input file for probing duration
    probe_path = input_file
    if not probe_path:
        for i, arg in enumerate(cmd):
            if arg == '-i' and i + 1 < len(cmd):
                candidate = cmd[i + 1]
                # Skip pipe:, lavfi, nullsrc etc.
                if not candidate.startswith(('pipe:', 'anullsrc')) and '=' not in candidate:
                    probe_path = candidate
                    break

    if probe_path:
        try:
            probe_info = ffmpeg.probe(probe_path)
            duration = float(probe_info['format']['duration'])
        except (ffmpeg.Error, KeyError, ValueError):
            logging.warning(f"Could not probe duration from {probe_path}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task(description, total=100)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8',
            )
        except FileNotFoundError:
            console.print("[bold red]Error: ffmpeg not found. Is it installed and in PATH?[/bold red]")
            return False
        except Exception as e:
            console.print(f"[bold red]Failed to start process: {e}[/bold red]")
            return False

        stderr_buffer = deque(maxlen=15)

        for line in process.stderr:
            stderr_buffer.append(line)
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
                    pass

        process.wait()
        progress.update(task, completed=100)

        if process.returncode != 0:
            console.print("[bold red]An error occurred:[/bold red]")
            console.print("".join(stderr_buffer))
            logging.error(f"Command failed (exit {process.returncode})")
            return False

    logging.info("Command successful (with progress bar).")
    return True


def has_audio_stream(file_path):
    """Check if the media file has an audio stream."""
    try:
        probe = ffmpeg.probe(file_path, select_streams='a')
        return 'streams' in probe and len(probe['streams']) > 0
    except ffmpeg.Error:
        return False
