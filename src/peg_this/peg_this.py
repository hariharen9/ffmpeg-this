
import os
import subprocess
import json
from pathlib import Path
import sys
import logging

# --- Dependency Check ---
try:
    import questionary
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
except ImportError:
    print("Error: Required libraries 'questionary' and 'rich' are not installed.")
    print("Please install them by running: pip install questionary rich")
    sys.exit(1)

try:
    import ffmpeg
except ImportError:
    print("Error: The 'ffmpeg-python' library is not installed.")
    print("Please install it by running: pip install ffmpeg-python")
    sys.exit(1)

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from PIL import Image, ImageTk
except ImportError:
    tk = None
# --- End Dependency Check ---


# --- Global Configuration ---
# Configure logging
log_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ffmpeg_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w') # Overwrite log on each run
    ]
)

# Initialize Rich Console
console = Console()
# --- End Global Configuration ---


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
        console.print("Please install FFmpeg and ensure its location is in your system's PATH.")
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
                console.print(f"[bold red]An error occurred during processing. Check {log_file} for details.[/bold red]")
                return None
        
        logging.info("Command successful (with progress bar).")
        return "Success"


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


def inspect_file(file_path):
    """Show detailed information about the selected media file using ffprobe."""
    console.print(f"Inspecting {os.path.basename(file_path)}...")
    try:
        info = ffmpeg.probe(file_path)
    except ffmpeg.Error as e:
        console.print("[bold red]An error occurred while inspecting the file:[/bold red]")
        console.print(e.stderr.decode('utf-8'))
        logging.error(f"ffprobe error:{e.stderr.decode('utf-8')}")
        questionary.press_any_key_to_continue().ask()
        return

    format_info = info.get('format', {})
    table = Table(title=f"File Information: {os.path.basename(file_path)}", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    size_mb = float(format_info.get('size', 0)) / (1024 * 1024)
    duration_sec = float(format_info.get('duration', 0))
    bit_rate_kbps = float(format_info.get('bit_rate', 0)) / 1000

    table.add_row("Size", f"{size_mb:.2f} MB")
    table.add_row("Duration", f"{duration_sec:.2f} seconds")
    table.add_row("Format", format_info.get('format_long_name', 'N/A'))
    table.add_row("Bitrate", f"{bit_rate_kbps:.0f} kb/s")
    console.print(table)

    for stream_type in ['video', 'audio']:
        streams = [s for s in info.get('streams', []) if s.get('codec_type') == stream_type]
        if streams:
            stream_table = Table(title=f"{stream_type.capitalize()} Streams", show_header=True, header_style=f"bold {'cyan' if stream_type == 'video' else 'green'}")
            stream_table.add_column("Stream")
            stream_table.add_column("Codec")
            if stream_type == 'video':
                stream_table.add_column("Resolution")
                stream_table.add_column("Frame Rate")
            else:
                stream_table.add_column("Sample Rate")
                stream_table.add_column("Channels")
            
            for s in streams:
                if stream_type == 'video':
                    stream_table.add_row(f"#{s.get('index')}", s.get('codec_name'), f"{s.get('width')}x{s.get('height')}", s.get('r_frame_rate'))
                else:
                    stream_table.add_row(f"#{s.get('index')}", s.get('codec_name'), f"{s.get('sample_rate')} Hz", str(s.get('channels')))
            console.print(stream_table)

    questionary.press_any_key_to_continue().ask()


def has_audio_stream(file_path):
    """Check if the media file has an audio stream."""
    try:
        probe = ffmpeg.probe(file_path, select_streams='a')
        return 'streams' in probe and len(probe['streams']) > 0
    except ffmpeg.Error:
        return False


def convert_file(file_path):
    """Convert the file to a different format."""
    is_gif = Path(file_path).suffix.lower() == '.gif'
    has_audio = has_audio_stream(file_path)

    output_format = questionary.select("Select the output format:", choices=["mp4", "mkv", "mov", "avi", "webm", "mp3", "flac", "wav", "gif"], use_indicator=True).ask()
    if not output_format: return

    if (is_gif or not has_audio) and output_format in ["mp3", "flac", "wav"]:
        console.print("[bold red]Error: Source has no audio to convert.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return

    output_file = f"{Path(file_path).stem}_converted.{output_format}"
    
    input_stream = ffmpeg.input(file_path)
    output_stream = None
    kwargs = {'y': None}

    if output_format in ["mp4", "mkv", "mov", "avi", "webm"]:
        quality = questionary.select("Select quality preset:", choices=["Same as source", "High (CRF 18)", "Medium (CRF 23)", "Low (CRF 28)"], use_indicator=True).ask()
        if not quality: return

        if quality == "Same as source":
            kwargs['c'] = 'copy'
        else:
            crf = quality.split(" ")[-1][1:-1]
            kwargs['c:v'] = 'libx264'
            kwargs['crf'] = crf
            kwargs['pix_fmt'] = 'yuv420p'
            if has_audio:
                kwargs['c:a'] = 'aac'
                kwargs['b:a'] = '192k'
            else:
                kwargs['an'] = None
        output_stream = input_stream.output(output_file, **kwargs)

    elif output_format in ["mp3", "flac", "wav"]:
        kwargs['vn'] = None
        if output_format == 'mp3':
            bitrate = questionary.select("Select audio bitrate:", choices=["128k", "192k", "256k", "320k"]).ask()
            if not bitrate: return
            kwargs['c:a'] = 'libmp3lame'
            kwargs['b:a'] = bitrate
        else:
            kwargs['c:a'] = output_format
        output_stream = input_stream.output(output_file, **kwargs)

    elif output_format == "gif":
        fps = questionary.text("Enter frame rate (e.g., 15):", default="15").ask()
        if not fps: return
        scale = questionary.text("Enter width in pixels (e.g., 480):", default="480").ask()
        if not scale: return
        
        palette_file = f"palette_{Path(file_path).stem}.png"
        
        # Correctly chain filters for palette generation using explicit w/h arguments
        palette_gen_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos').filter('palettegen')
        run_command(palette_gen_stream.output(palette_file, y=None), "Generating color palette...")

        if not os.path.exists(palette_file):
            console.print("[bold red]Failed to generate color palette for GIF.[/bold red]")
            questionary.press_any_key_to_continue().ask()
            return

        palette_input = ffmpeg.input(palette_file)
        video_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos')
        
        final_stream = ffmpeg.filter([video_stream, palette_input], 'paletteuse')
        output_stream = final_stream.output(output_file, y=None)

    if output_stream and run_command(output_stream, f"Converting to {output_format}...", show_progress=True):
        console.print(f"[bold green]Successfully converted to {output_file}[/bold green]")
    else:
        console.print("[bold red]Conversion failed.[/bold red]")

    if output_format == "gif" and os.path.exists(f"palette_{Path(file_path).stem}.png"):
        os.remove(f"palette_{Path(file_path).stem}.png")
        
    questionary.press_any_key_to_continue().ask()


def trim_video(file_path):
    """Cut a video by specifying start and end times."""
    start_time = questionary.text("Enter start time (HH:MM:SS or seconds):").ask()
    if not start_time: return
    end_time = questionary.text("Enter end time (HH:MM:SS or seconds):").ask()
    if not end_time: return

    output_file = f"{Path(file_path).stem}_trimmed{Path(file_path).suffix}"
    
    stream = ffmpeg.input(file_path, ss=start_time, to=end_time).output(output_file, c='copy', y=None)
    
    run_command(stream, "Trimming video...", show_progress=True)
    console.print(f"[bold green]Successfully trimmed to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()


def extract_audio(file_path):
    """Extract the audio track from a video file."""
    if not has_audio_stream(file_path):
        console.print("[bold red]Error: No audio stream found in the file.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return

    audio_format = questionary.select("Select audio format:", choices=["mp3", "flac", "wav"], use_indicator=True).ask()
    if not audio_format: return

    output_file = f"{Path(file_path).stem}_audio.{audio_format}"
    stream = ffmpeg.input(file_path).output(output_file, vn=None, acodec='libmp3lame' if audio_format == 'mp3' else audio_format, y=None)
    
    run_command(stream, f"Extracting audio to {audio_format.upper()}...", show_progress=True)
    console.print(f"[bold green]Successfully extracted audio to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()


def remove_audio(file_path):
    """Create a silent version of a video."""
    output_file = f"{Path(file_path).stem}_no_audio{Path(file_path).suffix}"
    stream = ffmpeg.input(file_path).output(output_file, vcodec='copy', an=None, y=None)
    
    run_command(stream, "Removing audio track...", show_progress=True)
    console.print(f"[bold green]Successfully removed audio, saved to {output_file}[/bold green]")
    questionary.press_any_key_to_continue().ask()


def crop_video(file_path):
    """Visually crop a video by selecting an area."""
    if not tk:
        console.print("[bold red]Cannot perform visual cropping: tkinter & Pillow are not installed.[/bold red]")
        return

    preview_frame = f"preview_{Path(file_path).stem}.jpg"
    try:
        # Extract a frame from the middle of the video for preview
        probe = ffmpeg.probe(file_path)
        duration = float(probe['format']['duration'])
        mid_point = duration / 2
        
        # Corrected frame extraction command with `-q:v`
        run_command(
            ffmpeg.input(file_path, ss=mid_point).output(preview_frame, vframes=1, **{'q:v': 2}, y=None),
            "Extracting a frame for preview..."
        )

        if not os.path.exists(preview_frame):
            console.print("[bold red]Could not extract a frame from the video.[/bold red]")
            return

        # --- Tkinter GUI for Cropping ---
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
            rect_coords['x1'], rect_coords['y1'] = event.x, event.y
            rect_id = canvas.create_rectangle(0, 0, 1, 1, outline='red', width=2)

        def on_drag(event):
            rect_coords['x2'], rect_coords['y2'] = event.x, event.y
            canvas.coords(rect_id, rect_coords['x1'], rect_coords['y1'], rect_coords['x2'], rect_coords['y2'])

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        
        messagebox.showinfo("Instructions", "Click and drag to draw a cropping rectangle.\nClose this window when you are done.", parent=root)
        root.mainloop()

        # --- Cropping Logic ---
        crop_w = abs(rect_coords['x2'] - rect_coords['x1'])
        crop_h = abs(rect_coords['y2'] - rect_coords['y1'])
        crop_x = min(rect_coords['x1'], rect_coords['x2'])
        crop_y = min(rect_coords['y1'], rect_coords['y2'])

        if crop_w < 2 or crop_h < 2: # Avoid tiny, invalid crops
            console.print("[bold yellow]Cropping cancelled as no valid area was selected.[/bold yellow]")
            return

        console.print(f"Selected crop area: [bold]width={crop_w} height={crop_h} at (x={crop_x}, y={crop_y})[/bold]")

        output_file = f"{Path(file_path).stem}_cropped{Path(file_path).suffix}"
        
        input_stream = ffmpeg.input(file_path)
        video_stream = input_stream.video.filter('crop', w=crop_w, h=crop_h, x=crop_x, y=crop_y)
        
        kwargs = {'y': None} # Overwrite output
        # Check for audio and copy it if it exists
        if has_audio_stream(file_path):
            audio_stream = input_stream.audio
            kwargs['c:a'] = 'copy'
            stream = ffmpeg.output(video_stream, audio_stream, output_file, **kwargs)
        else:
            stream = ffmpeg.output(video_stream, output_file, **kwargs)

        run_command(stream, "Applying crop to video...", show_progress=True)
        console.print(f"[bold green]Successfully cropped video and saved to {output_file}[/bold green]")

    finally:
        if os.path.exists(preview_frame):
            os.remove(preview_frame)
        questionary.press_any_key_to_continue().ask()





def batch_convert():
    """Convert all media files in the directory to a specific format."""
    media_files = get_media_files()
    if not media_files:
        console.print("[bold yellow]No media files found in the current directory.[/bold yellow]")
        questionary.press_any_key_to_continue().ask()
        return

    output_format = questionary.select(
        "Select output format for the batch conversion:",
        choices=["mp4", "mkv", "mov", "avi", "webm", "mp3", "flac", "wav", "gif"],
        use_indicator=True
    ).ask()
    if not output_format: return

    quality_preset = None
    if output_format in ["mp4", "mkv", "mov", "avi", "webm"]:
        quality_preset = questionary.select(
            "Select quality preset:",
            choices=["Same as source", "High (CRF 18)", "Medium (CRF 23)", "Low (CRF 28)"],
            use_indicator=True
        ).ask()
        if not quality_preset: return

    confirm = questionary.confirm(
        f"This will convert {len(media_files)} file(s) in the current directory to .{output_format}. Continue?",
        default=False
    ).ask()

    if not confirm:
        console.print("[bold yellow]Batch conversion cancelled.[/bold yellow]")
        return

    success_count = 0
    fail_count = 0

    for file in media_files:
        console.rule(f"Processing: {file}")
        file_path = os.path.abspath(file)
        is_gif = Path(file_path).suffix.lower() == '.gif'
        has_audio = has_audio_stream(file_path)

        if (is_gif or not has_audio) and output_format in ["mp3", "flac", "wav"]:
            console.print(f"[bold yellow]Skipping {file}: Source has no audio to convert.[/bold yellow]")
            continue

        output_file = f"{Path(file_path).stem}_batch.{output_format}"
        input_stream = ffmpeg.input(file_path)
        output_stream = None
        kwargs = {'y': None}

        try:
            if output_format in ["mp4", "mkv", "mov", "avi", "webm"]:
                if quality_preset == "Same as source":
                    kwargs['c'] = 'copy'
                else:
                    crf = quality_preset.split(" ")[-1][1:-1]
                    kwargs['c:v'] = 'libx264'
                    kwargs['crf'] = crf
                    kwargs['pix_fmt'] = 'yuv420p'
                    if has_audio:
                        kwargs['c:a'] = 'aac'
                        kwargs['b:a'] = '192k'
                    else:
                        kwargs['an'] = None
                output_stream = input_stream.output(output_file, **kwargs)

            elif output_format in ["mp3", "flac", "wav"]:
                kwargs['vn'] = None
                kwargs['c:a'] = 'libmp3lame' if output_format == 'mp3' else output_format
                if output_format == 'mp3':
                    kwargs['b:a'] = '192k' # Default bitrate for batch
                output_stream = input_stream.output(output_file, **kwargs)

            elif output_format == "gif":
                fps = "15"
                scale = "480"
                palette_file = f"palette_{Path(file_path).stem}.png"
                
                palette_gen_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos').filter('palettegen')
                run_command(palette_gen_stream.output(palette_file, y=None), f"Generating palette for {file}...")

                if not os.path.exists(palette_file):
                    console.print(f"[bold red]Failed to generate color palette for {file}.[/bold red]")
                    fail_count += 1
                    continue

                palette_input = ffmpeg.input(palette_file)
                video_stream = input_stream.video.filter('fps', fps=fps).filter('scale', w=scale, h=-1, flags='lanczos')
                final_stream = ffmpeg.filter([video_stream, palette_input], 'paletteuse')
                output_stream = final_stream.output(output_file, y=None)

            if output_stream and run_command(output_stream, f"Converting {file}...", show_progress=True):
                console.print(f"  -> [bold green]Successfully converted to {output_file}[/bold green]")
                success_count += 1
            else:
                console.print(f"  -> [bold red]Failed to convert {file}.[/bold red]")
                fail_count += 1

            if output_format == "gif" and os.path.exists(f"palette_{Path(file_path).stem}.png"):
                os.remove(f"palette_{Path(file_path).stem}.png")

        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred while processing {file}: {e}[/bold red]")
            logging.error(f"Batch convert error for file {file}: {e}")
            fail_count += 1

    console.rule("[bold green]Batch Conversion Complete[/bold green]")
    console.print(f"Successful: {success_count} | Failed: {fail_count}")
    questionary.press_any_key_to_continue().ask()


def action_menu(file_path):
    """Display the menu of actions for a selected file."""
    while True:
        console.rule(f"[bold]Actions for: {os.path.basename(file_path)}[/bold]")
        action = questionary.select(
            "Choose an action:",
            choices=[
                "Inspect File Details",
                "Convert",
                "Trim Video",
                "Crop Video (Visual)",
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
            "Crop Video (Visual)": crop_video,
            "Extract Audio": extract_audio,
            "Remove Audio": remove_audio,
        }
        # Ensure we have a valid action before calling
        if action in actions:
            actions[action](file_path)


def join_videos():
    """Join multiple videos into a single file after standardizing their resolutions and sample rates."""
    console.print("[bold cyan]Select videos to join (in order). Press Enter when done.[/bold cyan]")
    
    media_files = get_media_files()
    video_files = [f for f in media_files if Path(f).suffix.lower() in [".mp4", ".mkv", ".mov", ".avi", ".webm"]]

    if len(video_files) < 2:
        console.print("[bold yellow]Not enough video files in the directory to join.[/bold yellow]")
        questionary.press_any_key_to_continue().ask()
        return

    selected_videos = questionary.checkbox("Select at least two videos to join in order:", choices=video_files).ask()

    if not selected_videos or len(selected_videos) < 2:
        console.print("[bold yellow]Joining cancelled. At least two videos must be selected.[/bold yellow]")
        return

    console.print("Videos will be joined in this order:")
    for i, video in enumerate(selected_videos):
        console.print(f"  {i+1}. {video}")

    output_file = questionary.text("Enter the output file name:", default="joined_video.mp4").ask()
    if not output_file: return

    try:
        first_video_path = os.path.abspath(selected_videos[0])
        probe = ffmpeg.probe(first_video_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        audio_info = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
        
        target_width = video_info['width']
        target_height = video_info['height']
        target_sar = video_info.get('sample_aspect_ratio', '1:1')
        target_sample_rate = audio_info['sample_rate']

    except Exception as e:
        console.print(f"[bold red]Could not probe first video for target parameters: {e}[/bold red]")
        return

    console.print(f"Standardizing all videos to: {target_width}x{target_height} resolution and {target_sample_rate} Hz audio.")

    processed_streams = []
    for video_file in selected_videos:
        stream = ffmpeg.input(os.path.abspath(video_file))
        v = (
            stream.video
            .filter('scale', w=target_width, h=target_height, force_original_aspect_ratio='decrease')
            .filter('pad', w=target_width, h=target_height, x='(ow-iw)/2', y='(oh-ih)/2')
            .filter('setsar', sar=target_sar.replace(':','/'))
            .filter('setpts', 'PTS-STARTPTS')
        )
        a = (
            stream.audio
            .filter('aresample', sample_rate=target_sample_rate)
            .filter('asetpts', 'PTS-STARTPTS')
        )
        processed_streams.append(v)
        processed_streams.append(a)

    joined = ffmpeg.concat(*processed_streams, v=1, a=1).node
    output_stream = ffmpeg.output(joined[0], joined[1], output_file, **{'c:v': 'libx264', 'crf': 23, 'c:a': 'aac', 'b:a': '192k', 'y': None})

    if run_command(output_stream, "Joining and re-encoding videos...", show_progress=True):
        console.print(f"[bold green]Successfully joined videos into {output_file}[/bold green]")
    else:
        console.print("[bold red]Failed to join videos.[/bold red]")
    
    questionary.press_any_key_to_continue().ask()


def main_menu():
    """Display the main menu."""
    check_ffmpeg_ffprobe()
    while True:
        console.rule("[bold magenta]ffmPEG-this[/bold magenta]")
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Process a Single Media File",
                "Join Multiple Videos",
                "Batch Convert All Media in Directory",
                "Exit"
            ],
            use_indicator=True
        ).ask()

        if choice is None or choice == "Exit":
            console.print("[bold]Goodbye![/bold]")
            break
        elif choice == "Process a Single Media File":
            selected_file = select_media_file()
            if selected_file:
                action_menu(selected_file)
        elif choice == "Join Multiple Videos":
            join_videos()
        elif choice == "Batch Convert All Media in Directory":
            batch_convert()


def main():
    """Main entry point for the application script."""
    try:
        main_menu()
    except (KeyboardInterrupt, EOFError):
        logging.info("Operation cancelled by user.")
        console.print("[bold]Operation cancelled. Goodbye![/bold]")
    except Exception as e:
        logging.exception("An unexpected error occurred.")
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        console.print(f"Details have been logged to {log_file}")

if __name__ == "__main__":
    main()