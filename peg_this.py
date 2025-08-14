import os
import subprocess
import json
from pathlib import Path
import sys
import random
import logging

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from PIL import Image, ImageTk
except ImportError:
    tk = None

try:
    import questionary
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
except ImportError:
    print("Required libraries not found. Please install them by running:")
    print("pip install questionary rich")
    sys.exit(1)

# Configure logging
log_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ffmpeg_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        # You can also add a handler to print to console, for development
        # logging.StreamHandler()
    ]
)

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
                    ("Media Files", "*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv *.mp3 *.flac *.wav *.ogg"),
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
        choices=["mp4", "mkv", "mov", "avi", "webm"],
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

def convert_to_gif(file_path):
    """Convert a video file to a high-quality GIF."""
    fps = questionary.text("Enter frame rate (e.g., 15):", default="15").ask()
    if not fps: return

    scale = questionary.text("Enter width in pixels (e.g., 480):", default="480").ask()
    if not scale: return

    output_file = f"{Path(file_path).stem}.gif"
    palette_file = "palette.png"

    palette_command = f'ffmpeg -i "{file_path}" -vf "fps={fps},scale={scale}:-1:flags=lanczos,palettegen" -y "{palette_file}"'
    run_command(palette_command, "Generating color palette...")

    gif_command = f'ffmpeg -i "{file_path}" -i "{palette_file}" -filter_complex "[0:v]fps={fps},scale={scale}:-1:flags=lanczos[x];[x][1:v]paletteuse" -y "{output_file}"'
    run_command(gif_command, f"Converting to GIF at {fps}fps...", show_progress=True)

    try:
        os.remove(palette_file)
    except OSError as e:
        console.print(f"[bold red]Error removing palette file {palette_file}: {e}[/bold red]")

    console.print(f"[bold green]Successfully created GIF: {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()

def batch_convert():
    """Convert all video files in the directory to a specific format."""
    output_format = questionary.select(
        "Select output format for the batch conversion:",
        choices=["mp4", "mkv", "mov", "avi", "webm", "gif"],
        use_indicator=True
    ).ask()

    if not output_format: return

    if output_format == 'gif':
        fps = questionary.text("Enter frame rate (e.g., 15):", default="15").ask()
        if not fps: return

        scale = questionary.text("Enter width in pixels (e.g., 480):", default="480").ask()
        if not scale: return

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
        if output_format == 'gif':
            output_file = f"{Path(file).stem}_batch.gif"
            palette_file = f"palette_{Path(file).stem}.png"

            palette_command = f'ffmpeg -i "{file}" -vf "fps={fps},scale={scale}:-1:flags=lanczos,palettegen" -y "{palette_file}"'
            run_command(palette_command, f"Generating color palette for {file}...")

            gif_command = f'ffmpeg -i "{file}" -i "{palette_file}" -filter_complex "[0:v]fps={fps},scale={scale}:-1:flags=lanczos[x];[x][1:v]paletteuse" -y "{output_file}"'
            run_command(gif_command, f"Converting {file} to GIF...", show_progress=True)

            try:
                os.remove(palette_file)
            except OSError as e:
                console.print(f"[bold red]Error removing palette file {palette_file}: {e}[/bold red]")
        else:
            output_file = f"{Path(file).stem}_batch.{output_format}"
            command = f'ffmpeg -i "{file}" -map 0 -c copy -c:s mov_text "{output_file}"'
            run_command(command, f"Converting {file}...", show_progress=True)

        console.print(f"  -> Saved as {output_file}")

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
        # Extract a frame from the middle of the video for preview
        info_command = f'ffprobe -v quiet -print_format json -show_streams "{file_path}"'
        logging.info(f"Running ffprobe to get video info: {info_command}")
        info_json = run_command(info_command)
        if not info_json:
            logging.error("ffprobe failed to get video info.")
            return

        info = json.loads(info_json)
        duration = float(info['streams'][0].get('duration', '0'))
        mid_point = duration / 2
        logging.info(f"Video duration: {duration}s, selected mid-point for frame: {mid_point}s")
        
        preview_frame = "preview.jpg"
        frame_command = f'ffmpeg -ss {mid_point} -i "{file_path}" -vframes 1 -q:v 2 "{preview_frame}" -y'
        logging.info(f"Running ffmpeg to extract frame: {frame_command}")
        run_command(frame_command, "Extracting a frame for preview...")

        if not os.path.exists(preview_frame):
            logging.error(f"Could not extract preview frame. File not found: {preview_frame}")
            console.print("[bold red]Could not extract a frame from the video.[/bold red]")
            return
        logging.info(f"Successfully extracted preview frame to {preview_frame}")

        # --- Tkinter GUI for Cropping ---
        root = tk.Tk()
        root.title("Crop Video - Drag to select area, close window to confirm")
        root.attributes("-topmost", True)

        img = Image.open(preview_frame)
        logging.info(f"Opened preview image with dimensions: {img.width}x{img.height}")
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
            pass # Final coords are set on drag
        
        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        messagebox.showinfo("Instructions", "Click and drag on the image to draw a cropping rectangle.\nClose this window when you are satisfied with the selection.", parent=root)
        
        logging.info("Showing crop selection window.")
        root.mainloop()
        logging.info("Crop selection window closed.")

        # --- Cropping Logic ---
        os.remove(preview_frame)

        x1, y1, x2, y2 = rect_coords['x1'], rect_coords['y1'], rect_coords['x2'], rect_coords['y2']
        
        # Ensure x1 < x2 and y1 < y2
        crop_x = min(x1, x2)
        crop_y = min(y1, y2)
        crop_w = abs(x2 - x1)
        crop_h = abs(y2 - y1)

        if crop_w == 0 or crop_h == 0:
            logging.warning("Cropping cancelled as no area was selected.")
            console.print("[bold yellow]Cropping cancelled as no area was selected.[/bold yellow]")
            return

        logging.info(f"Crop area calculated: W={crop_w}, H={crop_h}, X={crop_x}, Y={crop_y}")
        console.print(f"Selected crop area: [bold]width={crop_w} height={crop_h} at (x={crop_x}, y={crop_y})[/bold]")

        output_file = f"{Path(file_path).stem}_cropped{Path(file_path).suffix}"
        crop_command = f'ffmpeg -i "{file_path}" -vf "crop={crop_w}:{crop_h}:{crop_x}:{crop_y}" -c:a copy "{output_file}"'
        logging.info(f"Running ffmpeg crop command: {crop_command}")

        run_command(crop_command, "Applying crop to video...", show_progress=True)
        logging.info(f"Successfully cropped video and saved to {output_file}")
        console.print(f"[bold green]Successfully cropped video and saved to {output_file}[/bold green]")
        questionary.press_any_key_to_continue().ask()
    except Exception as e:
        logging.exception(f"An error occurred in crop_video for file: {file_path}")
        console.print(f"[bold red]An error occurred during the crop operation. Check {log_file} for details.[/bold red]")
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
                "Convert to GIF",
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
            "Convert (Lossless)": convert_lossless,
            "Convert (Smaller File Size)": convert_lossy,
            "Convert to GIF": convert_to_gif,
            "Trim Video": trim_video,
            "Crop Video": crop_video,
            "Extract Audio": extract_audio,
            "Remove Audio": remove_audio,
        }
        actions[action](file_path)

def main_menu():
    """Display the main menu."""
    check_ffmpeg_ffprobe()
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


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        logging.info("Operation cancelled by user.")
        console.print("\n[bold]Operation cancelled by user. Goodbye![/bold]")
    except Exception as e:
        logging.exception("An unexpected error occurred.")
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        console.print(f"Details have been logged to {log_file}")
