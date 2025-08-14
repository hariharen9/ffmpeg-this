import os
import ffmpeg
import json
from pathlib import Path
import sys
import random
import logging
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import questionary
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

# Configure logging
log_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ffmpeg_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
    ]
)

console = Console()


def run_command(stream, description="Processing...", show_progress=False):
    """Runs a command using ffmpeg-python, with an optional progress bar."""
    console.print(f"[bold cyan]{description}[/bold cyan]")

    if not show_progress:
        try:
            out, err = ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
            return out.decode('utf-8')
        except ffmpeg.Error as e:
            console.print("[bold red]An error occurred:[/bold red]")
            console.print(e.stderr.decode('utf-8'))
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
            process = ffmpeg.run_async(stream, pipe_stdout=True, pipe_stderr=True)

            # The following progress bar is a simulation, as ffmpeg-python does not directly expose progress.
            # A more accurate progress bar would require parsing ffmpeg's stderr.
            while process.poll() is None:
                progress.update(task, advance=0.5)
                # A more sophisticated implementation could read from process.stderr
                # and parse the progress information.
                import time
                time.sleep(0.1)

            progress.update(task, completed=100)
            out, err = process.communicate()
            if process.returncode != 0:
                console.print(f"[bold red]An error occurred during processing.[/bold red]")
                console.print(err.decode('utf-8'))
                return None
        return "Success"


def get_media_files():
    """Scan the current directory for media files."""
    media_extensions = [".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".wmv", ".mp3", ".flac", ".wav", ".ogg", ".gif"]
    files = [f for f in os.listdir('.') if os.path.isfile(f) and Path(f).suffix.lower() in media_extensions]
    return files


def select_media_file():
    """Display a menu to select a media file, or open a file picker if none are found."""
    media_files = get_media_files()
    if not media_files:
        console.print("[bold yellow]No media files found in this directory.[/bold yellow]")
        if tk and questionary.confirm("Would you like to select a file from another location?").ask():
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            file_path = filedialog.askopenfilename(
                title="Select a media file",
                filetypes=[
                    ("Media Files", "*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv *.mp3 *.flac *.wav *.ogg *.gif"),
                    ("All Files", "*.*")
                ]
            )
            return file_path
        else:
            return None

    file = questionary.select(
        "Select a media file to process:",
        choices=media_files + [questionary.Separator(), "Back"],
        use_indicator=True
    ).ask()

    return file if file != "Back" else None


def inspect_file(file_path):
    """Show detailed information about the selected media file."""
    try:
        info = ffmpeg.probe(file_path)
    except ffmpeg.Error as e:
        console.print("[bold red]An error occurred while inspecting the file:[/bold red]")
        console.print(e.stderr.decode('utf-8'))
        return

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


def trim_video(file_path):
    """Cut a video by specifying start and end times."""
    start_time = questionary.text("Enter start time (HH:MM:SS):").ask()
    if not start_time: return
    end_time = questionary.text("Enter end time (HH:MM:SS):").ask()
    if not end_time: return

    output_file = f"{Path(file_path).stem}_trimmed{Path(file_path).suffix}"
    stream = ffmpeg.input(file_path, ss=start_time, to=end_time).output(output_file, c='copy')
    run_command(stream, "Trimming video...", show_progress=True)
    console.print(f"[bold green]Successfully trimmed to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()

def extract_audio(file_path):
    """Extract the audio track from a video file."""
    audio_format = questionary.select(
        "Select audio format:",
        choices=[
            questionary.Choice("MP3 (lossy)", {"codec": "libmp3lame", "ext": "mp3", "q": 2}),
            questionary.Choice("FLAC (lossless)", {"codec": "flac", "ext": "flac"}),
            questionary.Choice("WAV (uncompressed)", {"codec": "pcm_s16le", "ext": "wav"})
        ],
        use_indicator=True
    ).ask()

    if not audio_format: return

    output_file = f"{Path(file_path).stem}_audio.{audio_format['ext']}"
    stream = ffmpeg.input(file_path).output(output_file, vn=None, acodec=audio_format['codec'], **({'q:a': audio_format['q']} if 'q' in audio_format else {}))
    run_command(stream, f"Extracting audio to {audio_format['ext'].upper()}...", show_progress=True)
    console.print(f"[bold green]Successfully extracted audio to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()

def remove_audio(file_path):
    """Create a silent version of a video."""
    output_file = f"{Path(file_path).stem}_no_audio{Path(file_path).suffix}"
    stream = ffmpeg.input(file_path).output(output_file, vcodec='copy', an=None)
    run_command(stream, "Removing audio track...", show_progress=True)
    console.print(f"[bold green]Successfully removed audio, saved to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()


def batch_convert():
    """Convert all media files in the directory to a specific format."""
    output_format = questionary.select(
        "Select output format for the batch conversion:",
        choices=["mp4", "mkv", "mov", "avi", "webm", "flv", "wmv", "mp3", "flac", "wav", "ogg", "m4a", "aac", "gif"],
        use_indicator=True
    ).ask()

    if not output_format: return

    quality = "copy"
    if output_format in ["mp4", "webm", "avi", "wmv"]:
        quality = questionary.select(
            "Select quality preset:",
            choices=["Same as source (lossless if possible)", "High Quality (CRF 18)", "Medium Quality (CRF 23)", "Low Quality (CRF 28)"],
            use_indicator=True
        ).ask()
        if not quality: return

    confirm = questionary.confirm(
        f"This will attempt to convert ALL media files in the current directory to .{output_format}. Are you sure?",
        default=False
    ).ask()

    if not confirm:
        console.print("[bold yellow]Batch conversion cancelled.[/bold yellow]")
        return

    media_files = get_media_files()

    for file in media_files:
        is_gif = Path(file).suffix.lower() == '.gif'
        has_audio = has_audio_stream(file)

        if is_gif and output_format in ["mp3", "flac", "wav", "ogg", "m4a", "aac"]:
            console.print(f"[bold yellow]Skipping {file}: Cannot convert a GIF to an audio format.[/bold yellow]")
            continue

        if not has_audio and output_format in ["mp3", "flac", "wav", "ogg", "m4a", "aac"]:
            console.print(f"[bold yellow]Skipping {file}: No audio stream found.[/bold yellow]")
            continue

        output_file = f"{Path(file).stem}_batch.{output_format}"
        stream = ffmpeg.input(file)

        if output_format in ["mp4", "webm", "avi", "wmv"]:
            if quality == "Same as source (lossless if possible)":
                stream = stream.output(output_file, c='copy')
            else:
                crf = quality.split(" ")[-1][1:-1]
                audio_kwargs = {'c:a': 'aac', 'b:a': '192k'} if has_audio else {'an': None}
                stream = stream.output(output_file, **{'c:v': 'libx264', 'crf': crf, 'pix_fmt': 'yuv420p'}, **audio_kwargs)
        elif output_format in ["mp3", "m4a", "aac"]:
            stream = stream.output(output_file, vn=None, acodec='libmp3lame', **{'b:a': '192k'})
        elif output_format in ["flac", "wav", "ogg"]:
            stream = stream.output(output_file, vn=None, acodec=output_format)
        elif output_format == "gif":
            fps = "15"
            scale = "480"
            palette_file = f"palette_{Path(file).stem}.png"
            palette_stream = ffmpeg.input(file).filter('fps', fps=fps).filter('scale', size=f"{scale}:-1", flags='lanczos').output(palette_file, y=None)
            run_command(palette_stream, f"Generating color palette for {file}...")
            stream = ffmpeg.input(file).overlay(ffmpeg.input(palette_file).filter('paletteuse')).output(output_file, y=None)


        if run_command(stream, f"Converting {file}...", show_progress=True):
            console.print(f"  -> Saved as {output_file}")
        else:
            console.print(f"[bold red]Failed to convert {file}.[/bold red]")

        if output_format == "gif" and os.path.exists(f"palette_{Path(file).stem}.png"):
            os.remove(f"palette_{Path(file).stem}.png")

    console.print("\n[bold green]Batch conversion finished.[/bold green]")
    questionary.press_any_key_to_continue().ask()

def crop_video(file_path):
    """Visually crop a video by selecting an area."""
    logging.info(f"Starting crop_video for {file_path}")
    if not tk:
        logging.error("Cannot perform cropping: tkinter/Pillow is not installed.")
        console.print("[bold red]Cannot perform cropping: tkinter/Pillow is not installed.[/bold red]")
        return

    try:
        info = ffmpeg.probe(file_path)
        duration = float(info['streams'][0].get('duration', '0'))
        mid_point = duration / 2
        
        preview_frame = "preview.jpg"
        stream = ffmpeg.input(file_path, ss=mid_point).output(preview_frame, vframes=1, qv=2, y=None)
        run_command(stream, "Extracting a frame for preview...")

        if not os.path.exists(preview_frame):
            logging.error(f"Could not extract preview frame. File not found: {preview_frame}")
            console.print("[bold red]Could not extract a frame from the video.[/bold red]")
            return
        logging.info(f"Successfully extracted preview frame to {preview_frame}")

        root = tk.Tk()
        root.title("Crop Video - Drag to select area, close window to confirm")
        root.attributes("-topmost", True)

        img = Image.open(preview_frame)
        img_tk = ImageTk.PhotoImage(img)

        canvas = tk.Canvas(root, width=img.width, height=img.height, cursor="cross")
        canvas.pack()
        canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)

        rect_coords = {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
        rect_id = None

        def on_press(event):
            nonlocal rect_id
            rect_coords['x1'] = event.x
            rect_coords['y1'] = event.y
            rect_id = canvas.create_rectangle(0, 0, 1, 1, outline='red', width=2)

        def on_drag(event):
            nonlocal rect_id
            rect_coords['x2'] = event.x
            rect_coords['y2'] = event.y
            canvas.coords(rect_id, rect_coords['x1'], rect_coords['y1'], rect_coords['x2'], rect_coords['y2'])

        def on_release(event):
            pass
        
        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        messagebox.showinfo("Instructions", "Click and drag on the image to draw a cropping rectangle.\nClose this window when you are satisfied with the selection.", parent=root)
        
        root.mainloop()

        os.remove(preview_frame)

        x1, y1, x2, y2 = rect_coords['x1'], rect_coords['y1'], rect_coords['x2'], rect_coords['y2']
        
        crop_x = min(x1, x2)
        crop_y = min(y1, y2)
        crop_w = abs(x2 - x1)
        crop_h = abs(y2 - y1)

        if crop_w == 0 or crop_h == 0:
            console.print("[bold yellow]Cropping cancelled as no area was selected.[/bold yellow]")
            return

        console.print(f"Selected crop area: [bold]width={crop_w} height={crop_h} at (x={crop_x}, y={crop_y})[/bold]")

        output_file = f"{Path(file_path).stem}_cropped{Path(file_path).suffix}"
        stream = ffmpeg.input(file_path).filter('crop', crop_w, crop_h, crop_x, crop_y).output(output_file, **{'c:a': 'copy'})
        run_command(stream, "Applying crop to video...", show_progress=True)
        console.print(f"[bold green]Successfully cropped video and saved to {output_file}[/bold green]")
        questionary.press_any_key_to_continue().ask()
    except Exception as e:
        logging.exception(f"An error occurred in crop_video for file: {file_path}")
        console.print(f"[bold red]An error occurred during the crop operation. Check {log_file} for details.[/bold red]")
        questionary.press_any_key_to_continue().ask()

def has_audio_stream(file_path):
    """Check if the media file has an audio stream."""
    try:
        info = ffmpeg.probe(file_path)
        return any(s for s in info.get('streams', []) if s.get('codec_type') == 'audio')
    except ffmpeg.Error as e:
        logging.error(f"Error checking for audio stream in {file_path}: {e.stderr.decode('utf-8')}")
    return False

def convert_file(file_path):
    """Convert the file to a different format."""
    is_gif = Path(file_path).suffix.lower() == '.gif'
    has_audio = has_audio_stream(file_path)

    output_format = questionary.select(
        "Select the output format:",
        choices=["mp4", "mkv", "mov", "avi", "webm", "flv", "wmv", "mp3", "flac", "wav", "ogg", "m4a", "aac", "gif"],
        use_indicator=True
    ).ask()

    if not output_format:
        return

    if is_gif and output_format in ["mp3", "flac", "wav", "ogg", "m4a", "aac"]:
        console.print("[bold red]Error: Cannot convert a GIF (no audio) to an audio format.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return
        
    if not has_audio and output_format in ["mp3", "flac", "wav", "ogg", "m4a", "aac"]:
        console.print("[bold red]Error: The source file has no audio stream to convert.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return

    output_file = f"{Path(file_path).stem}_converted.{output_format}"
    stream = ffmpeg.input(file_path)

    if output_format in ["mp4", "webm", "avi", "wmv"]:
        quality = questionary.select(
            "Select quality preset:",
            choices=["Same as source (lossless if possible)", "High Quality (CRF 18)", "Medium Quality (CRF 23)", "Low Quality (CRF 28)"],
            use_indicator=True
        ).ask()

        if not quality: return

        if quality == "Same as source (lossless if possible)":
            stream = stream.output(output_file, c='copy')
        else:
            crf = quality.split(" ")[-1][1:-1]
            audio_kwargs = {'c:a': 'aac', 'b:a': '192k'} if has_audio else {'an': None}
            stream = stream.output(output_file, **{'c:v': 'libx264', 'crf': crf, 'pix_fmt': 'yuv420p'}, **audio_kwargs)

    elif output_format in ["mp3", "m4a", "aac"]:
        bitrate = questionary.select("Select audio bitrate:", choices=["128k", "192k", "256k", "320k"]).ask()
        if not bitrate: return
        stream = stream.output(output_file, vn=None, acodec='libmp3lame', **{'b:a': bitrate})

    elif output_format in ["flac", "wav", "ogg"]:
        stream = stream.output(output_file, vn=None, acodec=output_format)

    elif output_format == "gif":
        fps = questionary.text("Enter frame rate (e.g., 15):", default="15").ask()
        if not fps: return
        scale = questionary.text("Enter width in pixels (e.g., 480):", default="480").ask()
        if not scale: return
        
        palette_file = "palette.png"
        palette_stream = ffmpeg.input(file_path).filter('fps', fps=fps).filter('scale', size=f"{scale}:-1", flags='lanczos').output(palette_file, y=None)
        run_command(palette_stream, "Generating color palette...")
        stream = ffmpeg.input(file_path).overlay(ffmpeg.input(palette_file).filter('paletteuse')).output(output_file, y=None)

    if run_command(stream, f"Converting to {output_format}...", show_progress=True):
        console.print(f"[bold green]Successfully converted to {output_file}[/bold green]")
    else:
        console.print("[bold red]Conversion failed. Please check the logs for more details.[/bold red]")

    if output_format == "gif" and os.path.exists("palette.png"):
        os.remove("palette.png")
        
    questionary.press_any_key_to_continue().ask()


def action_menu(file_path):
    """Display the menu of actions for a selected file."""
    while True:
        console.rule(f"[bold]Actions for: {file_path}[/bold]")
        action = questionary.select(
            "Choose an action:",
            choices=[
                "Inspect File Details",
                "Convert",
                "Trim Video",
                "Crop Video",
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
            "Convert": convert_file,
            "Trim Video": trim_video,
            "Crop Video": crop_video,
            "Extract Audio": extract_audio,
            "Remove Audio": remove_audio,
        }
        actions[action](file_path)

def main_menu():
    """Display the main menu."""
    while True:
        console.rule("[bold magenta]ffmPEG-this[/bold magenta]")
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


def main():
    try:
        main_menu()
    except KeyboardInterrupt:
        logging.info("Operation cancelled by user.")
        console.print("\n[bold]Operation cancelled by user. Goodbye![/bold]")
    except Exception as e:
        logging.exception("An unexpected error occurred.")
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        console.print(f"Details have been logged to {log_file}")

if __name__ == "__main__":
    main()