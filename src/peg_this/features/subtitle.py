
import os
import subprocess
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream

console = Console()

def is_whisper_supported():
    """Check if the installed ffmpeg supports the whisper filter."""
    try:
        # Run ffmpeg -filters and check output for 'whisper'
        result = subprocess.run(['ffmpeg', '-filters'], capture_output=True, text=True)
        return 'whisper' in result.stdout
    except Exception:
        return False

def generate_subtitles(file_path):
    """Generate subtitles for a video/audio file using FFmpeg's whisper filter."""
    if not has_audio_stream(file_path):
        console.print("[bold red]Error: File has no audio stream to transcribe.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return

    # 1. Check for FFmpeg Whisper Support
    if not is_whisper_supported():
        console.print("[bold red]Error: Your FFmpeg installation does not support the 'whisper' filter.[/bold red]")
        console.print("[yellow]To use this feature, you need FFmpeg 8.0+ compiled with --enable-whisper.[/yellow]")
        console.print("On macOS, standard Homebrew builds do not yet include this.")
        console.print("You may need to compile FFmpeg from source or wait for package updates.")
        questionary.press_any_key_to_continue().ask()
        return

    # 2. Get Model Path
    console.print("\n[bold cyan]FFmpeg Whisper Subtitling[/bold cyan]")
    console.print("You need a GGML Whisper model file (e.g., ggml-medium.en.bin).")
    console.print("Download models from: https://huggingface.co/ggerganov/whisper.cpp/tree/main")
    
    # Default model path suggestion (current dir or a models dir)
    default_model = "ggml-medium.en.bin"
    
    model_path = questionary.path(
        "Path to Whisper Model (.bin):",
        default=default_model,
        validate=lambda text: True if os.path.exists(text) and text.endswith('.bin') else "File not found or invalid extension"
    ).ask()
    
    if not model_path: return

    # 3. Get Options
    language = questionary.text("Language (e.g., en, fr, auto):", default="en").ask()
    if not language: return

    output_format = questionary.select(
        "Output Format:",
        choices=["srt", "vtt", "lrc", "json"],
        default="srt"
    ).ask()
    
    filename = Path(file_path).stem
    output_file = f"{filename}_subtitles.{output_format}"
    
    # 4. Construct Command
    # ffmpeg -i input -vn -af "whisper=model=...:language=...:destination=..." -f null -
    
    try:
        # Build the filter string
        # Note: We use absolute paths to be safe
        abs_model_path = os.path.abspath(model_path)
        abs_output_path = os.path.abspath(output_file)
        
        # We construct the filter args manually to ensure correct formatting
        whisper_filter_args = f"model={abs_model_path}:language={language}:destination={abs_output_path}:format={output_format}"
        
        # Construct the stream
        stream = ffmpeg.input(file_path)
        stream = stream.audio.filter('whisper', model=abs_model_path, language=language, destination=abs_output_path, format=output_format)
        
        # Output to null sink
        stream = stream.output("-", f="null")
        
        if run_command(stream, f"Generating subtitles ({language})... This may take a while.", show_progress=True):
             console.print(f"[bold green]Successfully generated subtitles: {output_file}[/bold green]")
        else:
             console.print("[bold red]Subtitle generation failed.[/bold red]")

    except Exception as e:
        console.print(f"[bold red]An error occurred: {e}[/bold red]")

    questionary.press_any_key_to_continue().ask()
