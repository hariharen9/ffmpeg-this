
import os
import subprocess
import platform
from pathlib import Path

import questionary
from prompt_toolkit.keys import Keys
from rich.console import Console

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


def open_native_file_picker(file_type_label, filetypes):
    """
    Open the native OS file picker dialog using subprocess.
    This runs in a separate process to avoid blocking the main event loop.
    """
    system = platform.system()

    try:
        if system == 'Darwin':  # macOS
            # Use osascript to open native file picker
            # Build file type filter for AppleScript
            extensions = []
            for _, pattern in filetypes:
                if pattern != "*.*":
                    exts = pattern.replace("*.", "").split()
                    extensions.extend(exts)

            if extensions:
                type_list = ", ".join([f'"{ext}"' for ext in extensions[:10]])  # Limit to 10
                script = f'''
                    set theFile to choose file with prompt "Select a {file_type_label} file" of type {{{type_list}}}
                    return POSIX path of theFile
                '''
            else:
                script = f'''
                    set theFile to choose file with prompt "Select a {file_type_label} file"
                    return POSIX path of theFile
                '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None

        elif system == 'Windows':
            # Use PowerShell to open native file picker
            extensions = []
            for _, pattern in filetypes:
                if pattern != "*.*":
                    exts = pattern.replace("*", "").split()
                    extensions.extend(exts)

            if extensions:
                filter_str = f"{file_type_label} files|*" + ";*".join(extensions[:15]) + "|All files|*.*"
            else:
                filter_str = "All files|*.*"

            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            $dialog = New-Object System.Windows.Forms.OpenFileDialog
            $dialog.Title = "Select a {file_type_label} file"
            $dialog.Filter = "{filter_str}"
            $dialog.ShowDialog() | Out-Null
            $dialog.FileName
            '''

            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None

        else:  # Linux
            # Try zenity first (GNOME), then kdialog (KDE)
            extensions = []
            for _, pattern in filetypes:
                if pattern != "*.*":
                    exts = pattern.split()
                    extensions.extend(exts)

            # Try zenity
            try:
                cmd = ['zenity', '--file-selection', f'--title=Select a {file_type_label} file']
                if extensions:
                    for ext in extensions[:10]:
                        cmd.extend(['--file-filter', ext])

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except FileNotFoundError:
                pass

            # Try kdialog
            try:
                filter_str = " ".join(extensions[:10]) if extensions else "*"
                result = subprocess.run(
                    ['kdialog', '--getopenfilename', '.', filter_str],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except FileNotFoundError:
                pass

            # Fallback: manual path input
            console.print("[yellow]No GUI file picker available (zenity/kdialog not found).[/yellow]")
            return _manual_path_input(file_type_label)

    except subprocess.TimeoutExpired:
        console.print("[yellow]File picker timed out.[/yellow]")
        return None
    except Exception as e:
        console.print(f"[yellow]File picker error: {e}[/yellow]")
        return _manual_path_input(file_type_label)


def _manual_path_input(file_type_label):
    """Fallback: ask user to manually enter a file path."""
    console.print("[dim]Enter the full path to the file, or press Enter to cancel.[/dim]")
    path = questionary.text(f"Path to {file_type_label} file:").ask()

    if path and os.path.isfile(path):
        return os.path.abspath(path)
    elif path:
        console.print("[bold red]File not found.[/bold red]")
    return None


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
        if questionary.confirm("Open file browser to select from another location?").ask():
            return open_native_file_picker(file_type_label, filetypes)
        return None

    # Add browse option to the choices
    choices = media_files + [questionary.Separator(), "📂 Browse...", "← Back"]
    show_file_select_help()
    file = select_file_with_search(f"Select a {file_type_label} file:", choices=choices)

    if file == "📂 Browse...":
        return open_native_file_picker(file_type_label, filetypes)

    return os.path.abspath(file) if file and file != "← Back" else None
