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
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

console = Console()


def _select_roi_with_opencv(image_path, window_title="Select Region"):
    """
    Use OpenCV's selectROI to let user draw a rectangle.
    Returns (x, y, width, height) or None if cancelled.
    """
    if not CV2_AVAILABLE:
        console.print("[bold red]OpenCV is not installed. Cannot perform visual selection.[/bold red]")
        console.print("[dim]Install with: pip install opencv-python[/dim]")
        return None

    img = cv2.imread(image_path)
    if img is None:
        console.print("[bold red]Could not load image for selection.[/bold red]")
        return None

    # Resize if too large for screen (keep aspect ratio)
    max_dim = 1200
    h, w = img.shape[:2]
    scale = 1.0
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img_display = cv2.resize(img, (int(w * scale), int(h * scale)))
    else:
        img_display = img.copy()

    console.print("[bold cyan]Instructions: Draw a rectangle with your mouse. Press ENTER or SPACE to confirm, C to cancel.[/bold cyan]")

    # Select ROI
    try:
        roi = cv2.selectROI(window_title, img_display, fromCenter=False, showCrosshair=True)
        cv2.destroyAllWindows()
    except Exception as e:
        cv2.destroyAllWindows()
        console.print(f"[bold red]Selection error: {e}[/bold red]")
        return None

    # roi is (x, y, w, h)
    x, y, rw, rh = roi

    if rw < 2 or rh < 2:
        return None

    # Scale back to original image coordinates
    if scale != 1.0:
        x = int(x / scale)
        y = int(y / scale)
        rw = int(rw / scale)
        rh = int(rh / scale)

    return (x, y, rw, rh)


def crop_video(file_path):
    if not CV2_AVAILABLE:
        console.print("[bold red]Cannot perform visual cropping: OpenCV is not installed.[/bold red]")
        console.print("[dim]Install with: pip install opencv-python[/dim]")
        press_continue()
        return

    if not validate_input_file(file_path):
        press_continue()
        return

    import tempfile
    preview_fd, preview_frame = tempfile.mkstemp(suffix=".jpg")
    os.close(preview_fd)

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

        # Use OpenCV for selection
        roi = _select_roi_with_opencv(preview_frame, "Crop Video - Draw rectangle, ENTER to confirm, C to cancel")

        if roi is None:
            console.print("[bold yellow]Cropping cancelled - no valid area selected.[/bold yellow]")
            press_continue()
            return

        crop_x, crop_y, crop_w, crop_h = roi
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
    if not CV2_AVAILABLE:
        console.print("[bold red]Cannot perform visual cropping: OpenCV is not installed.[/bold red]")
        console.print("[dim]Install with: pip install opencv-python[/dim]")
        press_continue()
        return

    if not validate_input_file(file_path):
        press_continue()
        return

    try:
        # Use OpenCV for selection
        roi = _select_roi_with_opencv(file_path, "Crop Image - Draw rectangle, ENTER to confirm, C to cancel")

        if roi is None:
            console.print("[bold yellow]Cropping cancelled - no valid area selected.[/bold yellow]")
            press_continue()
            return

        crop_x, crop_y, crop_w, crop_h = roi
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
