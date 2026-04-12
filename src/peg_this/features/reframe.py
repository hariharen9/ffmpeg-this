"""
AI Smart Reframe — auto-crop landscape video to portrait/square
using face tracking to keep the subject in frame.
"""
import os
import tempfile
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)

from peg_this.utils.ffmpeg_utils import has_audio_stream, run_command_list
from peg_this.utils.validation import (
    check_output_file,
    press_continue,
    validate_input_file,
)

console = Console()


# =============================================================================
# HELPERS
# =============================================================================

def _make_even(n):
    """Round down to nearest even number for encoder compatibility."""
    return n - (n % 2)


TARGET_ASPECTS = [
    ("9:16  (TikTok / Reels / Shorts)", 9, 16),
    ("1:1   (Square / Instagram)", 1, 1),
    ("4:5   (Instagram Portrait)", 4, 5),
]


# =============================================================================
# PHASE 1 — ANALYZE: DETECT FACES ACROSS SAMPLED FRAMES
# =============================================================================

def _analyze_faces(file_path, sample_interval, scale_factor, min_neighbors):
    """Sample frames and detect face center-X positions.

    Returns:
        frame_positions: dict mapping frame_index → center_x (int)
        total_frames: int
        fps: float
        width: int
        height: int
    """
    import cv2

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        console.print("[bold red]Error: Could not open video file.[/bold red]")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        console.print("[bold red]Error: Could not load Haar cascade.[/bold red]")
        cap.release()
        return None

    sampled_count = (total_frames // sample_interval) + 1
    frame_positions = {}  # frame_index → center_x

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing faces...", total=sampled_count)

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=scale_factor,
                    minNeighbors=min_neighbors,
                    minSize=(30, 30),
                )

                if len(faces) > 0:
                    # Pick the largest face (by area)
                    largest = max(faces, key=lambda f: f[2] * f[3])
                    x, y, w, h = largest
                    frame_positions[frame_idx] = x + w // 2
                progress.update(task, advance=1)

            frame_idx += 1

    cap.release()

    faces_found = len(frame_positions)
    console.print(
        f"[dim]Detected faces in {faces_found}/{sampled_count} sampled frames[/dim]"
    )

    return {
        "positions": frame_positions,
        "total_frames": total_frames,
        "fps": fps,
        "width": width,
        "height": height,
    }


# =============================================================================
# PHASE 2 — SMOOTH: BUILD PER-FRAME CROP X POSITIONS
# =============================================================================

def _build_smooth_positions(analysis, crop_w):
    """Interpolate and smooth face positions into per-frame crop-X values.

    Uses linear interpolation between detected frames, then applies
    exponential moving average for temporal smoothing.
    """
    positions = analysis["positions"]
    total_frames = analysis["total_frames"]
    width = analysis["width"]

    center_x_default = width // 2

    # Step 1: Build raw per-frame center_x via linear interpolation
    raw = [None] * total_frames

    if not positions:
        # No faces detected at all — use center
        return [_clamp_crop_x(center_x_default, crop_w, width)] * total_frames

    sorted_keys = sorted(positions.keys())

    # Fill before first detection
    for i in range(0, sorted_keys[0]):
        raw[i] = positions[sorted_keys[0]]

    # Interpolate between detections
    for k in range(len(sorted_keys) - 1):
        idx_a = sorted_keys[k]
        idx_b = sorted_keys[k + 1]
        val_a = positions[idx_a]
        val_b = positions[idx_b]
        span = idx_b - idx_a

        for i in range(idx_a, idx_b + 1):
            t = (i - idx_a) / span
            raw[i] = int(val_a + t * (val_b - val_a))

    # Fill after last detection
    last_val = positions[sorted_keys[-1]]
    for i in range(sorted_keys[-1], total_frames):
        raw[i] = last_val

    # Fill any remaining None gaps (shouldn't happen, but safety)
    for i in range(total_frames):
        if raw[i] is None:
            raw[i] = center_x_default

    # Step 2: Exponential moving average for smoothness
    alpha = 0.05  # Lower = smoother panning
    smoothed = [0] * total_frames
    smoothed[0] = float(raw[0])

    for i in range(1, total_frames):
        smoothed[i] = alpha * raw[i] + (1 - alpha) * smoothed[i - 1]

    # Step 3: Convert center_x → crop_x (top-left corner), clamped
    crop_positions = [
        _clamp_crop_x(int(cx), crop_w, width) for cx in smoothed
    ]

    return crop_positions


def _clamp_crop_x(center_x, crop_w, frame_w):
    """Convert face center_x to a clamped, even crop origin x."""
    x = center_x - crop_w // 2
    x = max(0, min(x, frame_w - crop_w))
    return _make_even(x)


# =============================================================================
# PHASE 3 — RENDER: CROP EACH FRAME AND WRITE OUTPUT
# =============================================================================

def _render_reframed(file_path, crop_positions, crop_w, crop_h, fps, final_output):
    """Read every frame, crop with per-frame X position, write output, merge audio."""
    import cv2

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        console.print("[bold red]Error: Could not reopen video.[/bold red]")
        return False

    total_frames = len(crop_positions)

    # Calculate crop Y (vertically centered)
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    crop_y = _make_even((frame_h - crop_h) // 2)
    crop_y = max(0, crop_y)

    # Write to temp file (no audio — OpenCV can't carry audio)
    temp_fd, temp_video = tempfile.mkstemp(suffix=".mp4")
    os.close(temp_fd)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(temp_video, fourcc, fps, (crop_w, crop_h))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Rendering reframe...", total=total_frames)

            idx = 0
            while True:
                ret, frame = cap.read()
                if not ret or idx >= total_frames:
                    break

                x = crop_positions[idx]
                cropped = frame[crop_y : crop_y + crop_h, x : x + crop_w]
                out.write(cropped)
                progress.update(task, advance=1)
                idx += 1

        cap.release()
        out.release()

        # Merge audio from original
        console.print("[bold cyan]Encoding final output...[/bold cyan]")

        from peg_this.settings import Settings
        settings = Settings()
        encoding_args = settings.get_encoder_list_args(quality="medium", crf=18)

        if has_audio_stream(file_path):
            merge_cmd = [
                "ffmpeg", "-y",
                "-i", temp_video,
                "-i", file_path,
            ]
            merge_cmd.extend(encoding_args)
            merge_cmd.extend([
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "1:a:0",
                "-shortest",
                final_output,
            ])
        else:
            merge_cmd = [
                "ffmpeg", "-y",
                "-i", temp_video,
            ]
            merge_cmd.extend(encoding_args)
            merge_cmd.append(final_output)

        if not run_command_list(merge_cmd, "Encoding final output...", show_progress=True, input_file=file_path):
            return False

        return True

    finally:
        if cap.isOpened():
            cap.release()
        if out.isOpened():
            out.release()
        if os.path.exists(temp_video):
            try:
                os.remove(temp_video)
            except Exception:
                pass


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def smart_reframe(file_path):
    """Auto-crop landscape video to portrait/square using face tracking."""
    try:
        import cv2
    except ImportError:
        console.print("[bold red]Missing dependency: opencv-python[/bold red]")
        console.print("[dim]Install with: pip install opencv-python[/dim]")
        press_continue()
        return

    if not validate_input_file(file_path):
        press_continue()
        return

    # Get video dimensions
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next(
            (s for s in probe["streams"] if s["codec_type"] == "video"), None
        )
        if not video_stream:
            console.print("[bold red]No video stream found.[/bold red]")
            press_continue()
            return

        src_w = int(video_stream["width"])
        src_h = int(video_stream["height"])
        duration = float(probe["format"].get("duration", 0))
    except Exception as e:
        console.print(f"[bold red]Could not probe video: {e}[/bold red]")
        press_continue()
        return

    console.print(f"[dim]Source: {src_w}x{src_h}, Duration: {duration:.1f}s[/dim]")

    # Target aspect ratio
    aspect_choices = [label for label, _, _ in TARGET_ASPECTS]
    aspect = questionary.select("Target aspect ratio:", choices=aspect_choices).ask()
    if aspect is None:
        return

    ratio_w, ratio_h = next(
        (rw, rh) for label, rw, rh in TARGET_ASPECTS if label == aspect
    )

    # Calculate crop dimensions
    target_ratio = ratio_w / ratio_h
    source_ratio = src_w / src_h

    if target_ratio >= source_ratio:
        # Target is wider or same — shouldn't normally happen for portrait crop
        crop_w = src_w
        crop_h = int(src_w / target_ratio)
    else:
        # Target is taller — crop width (the normal case for 16:9 → 9:16)
        crop_h = src_h
        crop_w = int(src_h * target_ratio)

    crop_w = _make_even(crop_w)
    crop_h = _make_even(crop_h)

    console.print(f"[dim]Output crop: {crop_w}x{crop_h}[/dim]")

    # Tracking mode
    mode = questionary.select(
        "Reframe mode:",
        choices=[
            "Auto (face tracking)",
            "Center crop (no tracking)",
        ],
    ).ask()
    if mode is None:
        return

    if "Center" in mode:
        # Simple center crop with ffmpeg — fast, no frame-by-frame
        _center_crop_ffmpeg(file_path, crop_w, crop_h, src_w, src_h)
        return

    # Detection sensitivity
    sensitivity = questionary.select(
        "Detection sensitivity:",
        choices=[
            "High (catches more faces, may have false positives)",
            "Medium (Recommended)",
            "Low (only confident detections)",
        ],
    ).ask()
    if sensitivity is None:
        return

    if "High" in sensitivity:
        scale_factor, min_neighbors = 1.1, 3
    elif "Low" in sensitivity:
        scale_factor, min_neighbors = 1.3, 7
    else:
        scale_factor, min_neighbors = 1.2, 5

    # Sample interval — balance speed vs accuracy
    total_frames_est = int(duration * 30) if duration > 0 else 1000
    if total_frames_est > 5000:
        sample_interval = 10
    elif total_frames_est > 1000:
        sample_interval = 5
    else:
        sample_interval = 3

    # ── Phase 1: Analyze ──
    analysis = _analyze_faces(file_path, sample_interval, scale_factor, min_neighbors)
    if analysis is None:
        press_continue()
        return

    # ── Phase 2: Smooth ──
    crop_positions = _build_smooth_positions(analysis, crop_w)

    # ── Output file ──
    stem = Path(file_path).stem
    suffix = Path(file_path).suffix
    ratio_tag = f"{ratio_w}x{ratio_h}"
    output_file = f"{stem}_reframed_{ratio_tag}{suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == "cancel":
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    # ── Phase 3: Render ──
    fps = analysis["fps"]
    success = _render_reframed(
        file_path, crop_positions, crop_w, crop_h, fps, final_output
    )

    if success:
        console.print(f"[bold green]Saved: {final_output}[/bold green]")
    else:
        console.print("[bold red]Reframe failed.[/bold red]")

    press_continue()


def _center_crop_ffmpeg(file_path, crop_w, crop_h, src_w, src_h):
    """Fast center crop using ffmpeg (no face tracking)."""
    from peg_this.utils.ffmpeg_utils import run_command, get_global_encoding_args

    stem = Path(file_path).stem
    suffix = Path(file_path).suffix
    output_file = f"{stem}_reframed_center{suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == "cancel":
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    crop_x = _make_even((src_w - crop_w) // 2)
    crop_y = _make_even((src_h - crop_h) // 2)

    encoding_args = get_global_encoding_args(crf=23)
    input_stream = ffmpeg.input(file_path)
    video = input_stream.video.filter("crop", w=crop_w, h=crop_h, x=crop_x, y=crop_y)

    if has_audio_stream(file_path):
        audio = input_stream.audio
        encoding_args["c:a"] = "copy"
        stream = ffmpeg.output(video, audio, final_output, **encoding_args)
    else:
        stream = ffmpeg.output(video, final_output, **encoding_args)

    if action_result == "overwrite":
        stream = stream.overwrite_output()

    if run_command(stream, "Applying center crop...", show_progress=True):
        console.print(f"[bold green]Saved: {final_output}[/bold green]")
    else:
        console.print("[bold red]Center crop failed.[/bold red]")

    press_continue()
