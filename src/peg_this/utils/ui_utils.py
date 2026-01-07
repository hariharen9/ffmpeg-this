
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

VIDEO_EXTENSIONS = [".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".wmv"]
AUDIO_EXTENSIONS = [".mp3", ".flac", ".wav", ".ogg"]
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"]
GIF_EXTENSIONS = [".gif"]

ALL_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS + IMAGE_EXTENSIONS + GIF_EXTENSIONS


def get_media_files(filter_type=None):
    if filter_type == "video":
        extensions = VIDEO_EXTENSIONS + GIF_EXTENSIONS
    elif filter_type == "image":
        extensions = IMAGE_EXTENSIONS
    elif filter_type == "audio":
        extensions = AUDIO_EXTENSIONS
    else:
        extensions = ALL_MEDIA_EXTENSIONS

    files = [f for f in os.listdir('.') if os.path.isfile(f) and Path(f).suffix.lower() in extensions]
    return files


def select_media_file(filter_type=None):
    media_files = get_media_files(filter_type)

    if filter_type == "video":
        file_type_label = "video"
        filetypes = [("Video Files", "*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv *.gif")]
    elif filter_type == "image":
        file_type_label = "image"
        filetypes = [("Image Files", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff")]
    elif filter_type == "audio":
        file_type_label = "audio"
        filetypes = [("Audio Files", "*.mp3 *.flac *.wav *.ogg")]
    else:
        file_type_label = "media"
        filetypes = [("Media Files", "*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv *.mp3 *.flac *.wav *.ogg *.gif *.jpg *.jpeg *.png *.webp *.bmp *.tiff")]

    filetypes.append(("All Files", "*.*"))

    if not media_files:
        console.print(f"[bold yellow]No {file_type_label} files found in this directory.[/bold yellow]")
        if tk and questionary.confirm("Select a file from another location?").ask():
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(
                title=f"Select a {file_type_label} file",
                filetypes=filetypes
            )
            return file_path if file_path else None
        return None

    choices = media_files + [questionary.Separator(), "← Back"]
    file = questionary.select(f"Select a {file_type_label} file:", choices=choices, use_indicator=True).ask()

    return os.path.abspath(file) if file and file != "← Back" else None
