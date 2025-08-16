
import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream

try:
    import tkinter as tk
    from tkinter import messagebox
    from PIL import Image, ImageTk
except ImportError:
    tk = None

console = Console()


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
