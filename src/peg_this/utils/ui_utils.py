
import os
import subprocess
import platform
from pathlib import Path

import questionary
from prompt_toolkit.keys import Keys
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


def get_inquirer_control(app):
    """Find the InquirerControl from the application layout."""
    def walk(container):
        yield container
        if hasattr(container, 'get_children'):
            for child in container.get_children():
                yield from walk(child)
        if hasattr(container, 'content'):
            yield from walk(container.content)

    for item in walk(app.layout.container):
        if hasattr(item, 'pointed_at') and hasattr(item, 'choices'):
            return item
    return None


def preview_file(file_path):
    """Open a file with the system's default application for preview."""
    system = platform.system()
    try:
        if system == 'Darwin':  # macOS
            subprocess.Popen(['open', file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == 'Windows':
            os.startfile(file_path)
        else:  # Linux
            subprocess.Popen(['xdg-open', file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # Silently fail if preview doesn't work


def select_with_back(message, choices):
    """Select prompt with backspace support for going back."""
    back_value = None
    for choice in choices:
        if isinstance(choice, str) and "← Back" in choice:
            back_value = choice
            break

    question = questionary.select(message, choices=choices, use_indicator=True)

    if back_value:
        kb = question.application.key_bindings

        @kb.add(Keys.Backspace, eager=True)
        @kb.add(Keys.Delete, eager=True)
        @kb.add(Keys.ControlH, eager=True)
        def handle_back(event):
            event.app.exit(result=back_value)

    return question.ask()


def select_file_with_search(message, choices, back_value="← Back"):
    """
    Enhanced file selector with search filtering and preview.
    - Type to search/filter files dynamically
    - Arrow keys to navigate
    - Backspace: clears search if searching, goes back if search is empty
    - 'p' to preview the highlighted file
    - Enter to select
    """
    question = questionary.select(
        message,
        choices=choices,
        use_indicator=True,
        use_search_filter=True,
        use_jk_keys=False,  # Disable j/k since they conflict with search
    )

    kb = question.application.key_bindings
    ic = get_inquirer_control(question.application)

    if ic:
        # Remove questionary's default backspace binding for search
        # so we can handle it ourselves (go back when search is empty)
        kb._bindings = [
            b for b in kb._bindings
            if not (hasattr(b, 'keys') and b.keys == (Keys.Backspace,))
        ]

        # Custom backspace: clear search char if searching, go back if empty
        @kb.add(Keys.Backspace, eager=True)
        @kb.add(Keys.ControlH, eager=True)
        def handle_backspace(event):
            if ic.search_filter:
                ic.remove_search_character()
            else:
                event.app.exit(result=back_value)

        # Preview with 'p' key
        @kb.add('p', eager=True)
        def handle_preview(event):
            current = ic.get_pointed_at()
            if current.value is None or current.value == back_value:
                return
            file_name = current.value
            if file_name and os.path.isfile(file_name):
                full_path = os.path.abspath(file_name)
                preview_file(full_path)

    return question.ask()


def show_file_select_help():
    """Show help bar for file selection with search and preview hints."""
    console.print(
        "[dim][[/dim][cyan]↑↓[/cyan][dim]] Navigate  "
        "[[/dim][cyan]Type[/cyan][dim]] Search  "
        "[[/dim][cyan]p[/cyan][dim]] Preview  "
        "[[/dim][cyan]Enter[/cyan][dim]] Select  "
        "[[/dim][cyan]Backspace[/cyan][dim]] Back[/dim]"
    )


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
    show_file_select_help()
    file = select_file_with_search(f"Select a {file_type_label} file:", choices=choices)

    return os.path.abspath(file) if file and file != "← Back" else None
