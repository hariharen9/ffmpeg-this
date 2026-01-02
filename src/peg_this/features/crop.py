import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, warn_reencode, press_continue
)

try:
    import tkinter as tk
    from PIL import Image, ImageTk
except ImportError:
    tk = None

console = Console()


def crop_video(file_path):
    if not tk:
        console.print("[bold red]Cannot perform visual cropping: tkinter & Pillow are not installed.[/bold red]")
        console.print("[dim]Install them with: pip install tk Pillow[/dim]")
        press_continue()
        return

    if not validate_input_file(file_path):
        press_continue()
        return

    preview_frame = f"preview_{Path(file_path).stem}.jpg"
    try:
        probe = ffmpeg.probe(file_path)
        duration = float(probe['format'].get('duration', 0))

        if duration <= 0:
            console.print("[bold red]Error: Could not determine video duration.[/bold red]")
            press_continue()
            return

        mid_point = duration / 2

        run_command(
            ffmpeg.input(file_path, ss=mid_point).output(preview_frame, vframes=1, **{'q:v': 2}).overwrite_output(),
            "Extracting a frame for preview..."
        )

        if not os.path.exists(preview_frame):
            console.print("[bold red]Could not extract a frame from the video.[/bold red]")
            press_continue()
            return

        root = tk.Tk()
        root.title("Crop Video - Drag to select area, close window to confirm")
        root.attributes("-topmost", True)

        img = Image.open(preview_frame)
        img_tk = ImageTk.PhotoImage(img, master=root)

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

        console.print("[bold cyan]Instructions: Click and drag to draw a cropping rectangle. Close the window when done.[/bold cyan]")
        root.lift()
        root.after_idle(root.attributes, '-topmost', False)

        root.mainloop()

        crop_w = abs(rect_coords['x2'] - rect_coords['x1'])
        crop_h = abs(rect_coords['y2'] - rect_coords['y1'])
        crop_x = min(rect_coords['x1'], rect_coords['x2'])
        crop_y = min(rect_coords['y1'], rect_coords['y2'])

        if crop_w < 2 or crop_h < 2:
            console.print("[bold yellow]Cropping cancelled as no valid area was selected.[/bold yellow]")
            return

        console.print(f"Selected crop area: [bold]width={crop_w} height={crop_h} at (x={crop_x}, y={crop_y})[/bold]")

        output_file = f"{Path(file_path).stem}_cropped{Path(file_path).suffix}"
        action_result, final_output = check_output_file(output_file, "Video file")

        if action_result == 'cancel':
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        warn_reencode("Video cropping")

        input_stream = ffmpeg.input(file_path)
        video_stream = input_stream.video.filter('crop', w=crop_w, h=crop_h, x=crop_x, y=crop_y)

        if has_audio_stream(file_path):
            audio_stream = input_stream.audio
            stream = ffmpeg.output(video_stream, audio_stream, final_output, **{'c:a': 'copy'})
        else:
            stream = ffmpeg.output(video_stream, final_output)

        if action_result == 'overwrite':
            stream = stream.overwrite_output()

        if run_command(stream, "Applying crop to video...", show_progress=True):
            console.print(f"[bold green]Successfully cropped video and saved to {final_output}[/bold green]")
        else:
            console.print("[bold red]Video cropping failed.[/bold red]")

    except Exception as e:
        console.print(f"[bold red]An error occurred: {e}[/bold red]")
    finally:
        if os.path.exists(preview_frame):
            os.remove(preview_frame)
        press_continue()


def crop_image(file_path):
    if not tk:
        console.print("[bold red]Cannot perform visual cropping: tkinter & Pillow are not installed.[/bold red]")
        console.print("[dim]Install them with: pip install tk Pillow[/dim]")
        press_continue()
        return

    if not validate_input_file(file_path):
        press_continue()
        return

    try:
        root = tk.Tk()
        root.title("Crop Image - Drag to select area, close window to confirm")
        root.attributes("-topmost", True)

        img = Image.open(file_path)

        max_width = root.winfo_screenwidth() - 100
        max_height = root.winfo_screenheight() - 100
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        img_tk = ImageTk.PhotoImage(img, master=root)

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

        console.print("[bold cyan]Instructions: Click and drag to draw a cropping rectangle. Close the window when done.[/bold cyan]")
        root.lift()
        root.after_idle(root.attributes, '-topmost', False)

        root.mainloop()

        crop_w = abs(rect_coords['x2'] - rect_coords['x1'])
        crop_h = abs(rect_coords['y2'] - rect_coords['y1'])
        crop_x = min(rect_coords['x1'], rect_coords['x2'])
        crop_y = min(rect_coords['y1'], rect_coords['y2'])

        if crop_w < 2 or crop_h < 2:
            console.print("[bold yellow]Cropping cancelled as no valid area was selected.[/bold yellow]")
            return

        console.print(f"Selected crop area: [bold]width={crop_w} height={crop_h} at (x={crop_x}, y={crop_y})[/bold]")

        output_file = f"{Path(file_path).stem}_cropped{Path(file_path).suffix}"
        action_result, final_output = check_output_file(output_file, "Image file")

        if action_result == 'cancel':
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        stream = ffmpeg.input(file_path).filter('crop', w=crop_w, h=crop_h, x=crop_x, y=crop_y).output(final_output)

        if action_result == 'overwrite':
            stream = stream.overwrite_output()

        if run_command(stream, "Applying crop to image..."):
            console.print(f"[bold green]Successfully cropped image and saved to {final_output}[/bold green]")
        else:
            console.print("[bold red]Image cropping failed.[/bold red]")

    except Exception as e:
        console.print(f"[bold red]An error occurred during cropping: {e}[/bold red]")
    finally:
        press_continue()
