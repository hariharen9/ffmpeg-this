
import os
from pathlib import Path

import questionary
from rich.console import Console

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None

console = Console()


def get_media_files():
    """Scan the current directory for media files."""
    media_extensions = [".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".wmv", ".mp3", ".flac", ".wav", ".ogg", ".gif"]
    files = [f for f in os.listdir('.') if os.path.isfile(f) and Path(f).suffix.lower() in media_extensions]
    return files


def select_media_file():
    """Display a menu to select a media file, or open a file picker."""
    media_files = get_media_files()
    if not media_files:
        console.print("[bold yellow]No media files found in this directory.[/bold yellow]")
        if tk and questionary.confirm("Would you like to select a file from another location?").ask():
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(
                title="Select a media file",
                filetypes=[("Media Files", "*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv *.mp3 *.flac *.wav *.ogg *.gif"), ("All Files", "*.*")]
            )
            return file_path if file_path else None
        return None

    choices = media_files + [questionary.Separator(), "Back"]
    file = questionary.select("Select a media file to process:", choices=choices, use_indicator=True).ask()
    
    # Return the absolute path to prevent "file not found" errors
    return os.path.abspath(file) if file and file != "Back" else None
