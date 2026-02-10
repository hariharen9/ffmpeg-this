import os
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream, get_global_encoding_args
from peg_this.utils.validation import (
    validate_input_file, check_output_file, warn_reencode, press_continue
)

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

console = Console()


def _make_even(n):
    """Round down to nearest even number. Video encoders require even dimensions."""
    return n - (n % 2)


def _calculate_preset_crop(source_w, source_h, ratio_w, ratio_h):
    """Calculate centered crop dimensions for a target aspect ratio.
    Returns (x, y, crop_w, crop_h) with even dimensions."""
    target_ratio = ratio_w / ratio_h
    source_ratio = source_w / source_h

    if target_ratio > source_ratio:
        # Target is wider than source — crop height
        crop_w = source_w
        crop_h = int(source_w / target_ratio)
    else:
        # Target is taller than source — crop width
        crop_h = source_h
        crop_w = int(source_h * target_ratio)

    crop_w = _make_even(crop_w)
    crop_h = _make_even(crop_h)

    # Center the crop
    x = _make_even((source_w - crop_w) // 2)
    y = _make_even((source_h - crop_h) // 2)

    return x, y, crop_w, crop_h


ASPECT_PRESETS = [
    ("16:9  (YouTube / Widescreen)", 16, 9),
    ("9:16  (TikTok / Reels / Shorts)", 9, 16),
    ("1:1   (Square / Instagram)", 1, 1),
    ("4:3   (Classic TV / iPad)", 4, 3),
    ("4:5   (Instagram Portrait)", 4, 5),
    ("21:9  (Ultrawide Cinema)", 21, 9),
    ("2.39:1 (Anamorphic Widescreen)", 239, 100),
    ("3:2   (Photo / DSLR)", 3, 2),
]


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
    if not validate_input_file(file_path):
        press_continue()
        return

    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        duration = float(probe['format'].get('duration', 0))

        if not video_stream:
            console.print("[bold red]Error: No video stream found.[/bold red]")
            press_continue()
            return

        source_w = int(video_stream['width'])
        source_h = int(video_stream['height'])
        console.print(f"[dim]Current resolution: {source_w}x{source_h}[/dim]")

        if duration <= 0:
            console.print("[bold red]Error: Could not determine video duration.[/bold red]")
            press_continue()
            return

        method = questionary.select(
            "How would you like to crop?",
            choices=[
                "Aspect ratio preset",
                "Visual selection (draw rectangle)",
                "← Back"
            ]
        ).ask()

        if method == "← Back" or method is None:
            return

        if "Aspect ratio" in method:
            # Build choices with resulting dimensions shown
            preset_choices = []
            for label, rw, rh in ASPECT_PRESETS:
                _, _, cw, ch = _calculate_preset_crop(source_w, source_h, rw, rh)
                if cw >= 2 and ch >= 2:
                    preset_choices.append(f"{label}  →  {cw}x{ch}")
            preset_choices.append("← Back")

            preset = questionary.select(
                "Select target aspect ratio:",
                choices=preset_choices
            ).ask()

            if preset == "← Back" or preset is None:
                return

            # Find the matching preset
            for label, rw, rh in ASPECT_PRESETS:
                if label in preset:
                    crop_x, crop_y, crop_w, crop_h = _calculate_preset_crop(source_w, source_h, rw, rh)
                    break
            else:
                return

            console.print(f"Crop area: [bold]{crop_w}x{crop_h}[/bold] centered at ({crop_x}, {crop_y})")

        else:
            # Visual selection
            if not CV2_AVAILABLE:
                console.print("[bold red]Cannot perform visual cropping: OpenCV is not installed.[/bold red]")
                console.print("[dim]Install with: pip install opencv-python[/dim]")
                press_continue()
                return

            import tempfile
            preview_fd, preview_frame = tempfile.mkstemp(suffix=".jpg")
            os.close(preview_fd)

            try:
                mid_point = duration / 2
                run_command(
                    ffmpeg.input(file_path, ss=mid_point).output(preview_frame, vframes=1, **{'q:v': 2}).overwrite_output(),
                    "Extracting a frame for preview..."
                )

                if not os.path.exists(preview_frame):
                    console.print("[bold red]Could not extract a frame from the video.[/bold red]")
                    press_continue()
                    return

                roi = _select_roi_with_opencv(preview_frame, "Crop Video - Draw rectangle, ENTER to confirm, C to cancel")

                if roi is None:
                    console.print("[bold yellow]Cropping cancelled - no valid area selected.[/bold yellow]")
                    press_continue()
                    return

                crop_x, crop_y, crop_w, crop_h = roi
            finally:
                if os.path.exists(preview_frame):
                    os.remove(preview_frame)

            # Enforce even dimensions for video encoding
            crop_w = _make_even(crop_w)
            crop_h = _make_even(crop_h)

            if crop_w < 2 or crop_h < 2:
                console.print("[bold red]Selected area too small after adjusting to even dimensions.[/bold red]")
                press_continue()
                return

            console.print(f"Selected crop area: [bold]{crop_w}x{crop_h}[/bold] at ({crop_x}, {crop_y})")

        output_file = f"{Path(file_path).stem}_cropped{Path(file_path).suffix}"
        action_result, final_output = check_output_file(output_file, "Video file")

        if action_result == 'cancel':
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        warn_reencode("Video cropping")

        encoding_args = get_global_encoding_args(crf=23)

        input_stream = ffmpeg.input(file_path)
        video_stream = input_stream.video.filter('crop', w=crop_w, h=crop_h, x=crop_x, y=crop_y)

        if has_audio_stream(file_path):
            audio_stream = input_stream.audio
            encoding_args['c:a'] = 'copy'
            stream = ffmpeg.output(video_stream, audio_stream, final_output, **encoding_args)
        else:
            stream = ffmpeg.output(video_stream, final_output, **encoding_args)

        if action_result == 'overwrite':
            stream = stream.overwrite_output()

        if run_command(stream, "Applying crop to video...", show_progress=True):
            console.print(f"[bold green]Successfully cropped video and saved to {final_output}[/bold green]")
        else:
            console.print("[bold red]Video cropping failed.[/bold red]")

    except Exception as e:
        console.print(f"[bold red]An error occurred: {e}[/bold red]")
    finally:
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
