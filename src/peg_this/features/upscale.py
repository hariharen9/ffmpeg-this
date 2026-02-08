"""
AI Video Upscaling Module - Real-ESRGAN + FFmpeg Fast Upscaling
"""
import os
import sys
import shutil
import tempfile
import numpy as np
import ffmpeg
import questionary
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, TaskProgressColumn

from peg_this.utils.ffmpeg_utils import has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, press_continue,
    format_duration, get_video_duration
)
from peg_this.settings import Settings

console = Console()

# ============================================================================
# MODEL DEFINITIONS
# ============================================================================

MODEL_INFO = {
    # Real-ESRGAN Models (RRDB architecture - high quality, slower)
    'RealESRGAN_x4plus': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
        'scale': 4,
        'arch': 'rrdb',
        'num_block': 23,
        'description': 'Best quality, slowest',
        'category': 'general'
    },
    'RealESRGAN_x2plus': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth',
        'scale': 2,
        'arch': 'rrdb',
        'num_block': 23,
        'description': '2x native, good for 1080p→4K',
        'category': 'general'
    },
    'RealESRNet_x4plus': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth',
        'scale': 4,
        'arch': 'rrdb',
        'num_block': 23,
        'description': 'Faster than x4plus, still good',
        'category': 'general'
    },
    # Anime Models
    'RealESRGAN_x4plus_anime_6B': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth',
        'scale': 4,
        'arch': 'rrdb',
        'num_block': 6,  # Smaller = faster
        'description': 'Anime/cartoon optimized',
        'category': 'anime'
    },
    # Compact/Fast Models (SRVGGNet architecture - fast, good quality)
    # These use num_conv=32, num_feat=64 for the x4v3 variants
    'realesr-animevideov3': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth',
        'scale': 4,
        'arch': 'compact',
        'num_conv': 16,  # animevideov3 uses 16 conv layers
        'num_feat': 64,
        'description': 'Fast anime video model',
        'category': 'anime'
    },
    'realesr-general-x4v3': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth',
        'scale': 4,
        'arch': 'compact',
        'num_conv': 32,  # general-x4v3 uses 32 conv layers
        'num_feat': 64,
        'description': 'Fast general purpose',
        'category': 'fast'
    },
    'realesr-general-wdn-x4v3': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth',
        'scale': 4,
        'arch': 'compact',
        'num_conv': 32,  # same as general-x4v3
        'num_feat': 64,
        'description': 'Fast + denoise',
        'category': 'fast'
    },
}

# FFmpeg upscale algorithms (no AI, very fast)
FFMPEG_ALGORITHMS = {
    'lanczos': 'Best quality (sharp)',
    'bicubic': 'Good quality (balanced)',
    'bilinear': 'Fast (smooth)',
    'neighbor': 'Fastest (pixelated - retro)',
    'spline': 'Very smooth gradients',
}


def _apply_torchvision_patch():
    """Monkey patch for torchvision > 0.16 compatibility with basicsr."""
    try:
        from torchvision.transforms import functional_tensor
    except ImportError:
        import torchvision.transforms.functional as F
        import types

        ft_module = types.ModuleType("torchvision.transforms.functional_tensor")
        ft_module.rgb_to_grayscale = F.rgb_to_grayscale
        sys.modules["torchvision.transforms.functional_tensor"] = ft_module


def _get_video_info(file_path):
    """Extract video metadata using ffprobe."""
    try:
        probe = ffmpeg.probe(file_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')

        width = int(video_info['width'])
        height = int(video_info['height'])

        # Parse frame rate safely
        fps_str = video_info.get('r_frame_rate', '30/1')
        if '/' in fps_str:
            num, den = map(int, fps_str.split('/'))
            fps = num / den if den != 0 else 30.0
        else:
            fps = float(fps_str)

        duration = float(probe['format'].get('duration', 0))

        # Get frame count - try multiple methods
        total_frames = int(video_info.get('nb_frames', 0))
        if total_frames == 0:
            total_frames = int(duration * fps)

        return {
            'width': width,
            'height': height,
            'fps': fps,
            'duration': duration,
            'total_frames': max(total_frames, 1),
            'codec': video_info.get('codec_name', 'unknown'),
            'pix_fmt': video_info.get('pix_fmt', 'unknown'),
        }
    except Exception as e:
        console.print(f"[bold red]Could not analyze video: {e}[/bold red]")
        return None


def _detect_hardware():
    """Detect available hardware acceleration."""
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            return {
                'device': torch.device('cuda'),
                'type': 'cuda',
                'name': gpu_name,
                'vram_gb': vram,
                'half_precision': True,
            }
        elif torch.backends.mps.is_available():
            return {
                'device': torch.device('mps'),
                'type': 'mps',
                'name': 'Apple Silicon',
                'vram_gb': None,  # Unified memory
                'half_precision': True,
            }
        else:
            return {
                'device': torch.device('cpu'),
                'type': 'cpu',
                'name': 'CPU',
                'vram_gb': None,
                'half_precision': False,
            }
    except ImportError:
        return None


def _download_model_weights(model_name, weights_dir):
    """Download model weights with progress bar."""
    import requests

    model_info = MODEL_INFO.get(model_name)
    if not model_info:
        console.print(f"[bold red]Unknown model: {model_name}[/bold red]")
        return None

    model_path = os.path.join(weights_dir, f"{model_name}.pth")

    if os.path.exists(model_path):
        return model_path

    url = model_info['url']
    console.print(f"[cyan]Downloading {model_name} weights...[/cyan]")

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Downloading...", total=total_size)

            with open(model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))

        console.print("[green]Download complete.[/green]")
        return model_path

    except Exception as e:
        console.print(f"[bold red]Failed to download weights: {e}[/bold red]")
        if os.path.exists(model_path):
            os.remove(model_path)
        return None


def _create_upsampler(model_name, device, tile_size, half_precision=True):
    """Initialize the Real-ESRGAN upsampler."""
    _apply_torchvision_patch()

    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer
    from realesrgan.archs.srvgg_arch import SRVGGNetCompact

    model_info = MODEL_INFO[model_name]

    # Build model architecture
    if model_info['arch'] == 'rrdb':
        model = RRDBNet(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_block=model_info['num_block'],
            num_grow_ch=32,
            scale=model_info['scale']
        )
    elif model_info['arch'] == 'compact':
        model = SRVGGNetCompact(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=model_info.get('num_feat', 64),
            num_conv=model_info.get('num_conv', 16),
            upscale=model_info['scale'],
            act_type='prelu'
        )
    else:
        raise ValueError(f"Unknown architecture: {model_info['arch']}")

    # Get weights
    weights_dir = os.path.join(os.path.expanduser("~"), ".peg_this", "weights")
    os.makedirs(weights_dir, exist_ok=True)

    model_path = _download_model_weights(model_name, weights_dir)
    if not model_path:
        return None

    # Create upsampler
    upsampler = RealESRGANer(
        scale=model_info['scale'],
        model_path=model_path,
        model=model,
        tile=tile_size,
        tile_pad=10,
        pre_pad=0,
        half=half_precision and device.type != 'cpu',
        device=device,
    )

    return upsampler


def _estimate_processing_time(total_frames, fps, hw_type, model_category, output_pixels):
    """Rough estimate of processing time based on output size."""
    # Base fps for 1080p output, scales down with resolution
    base_fps = {
        'cuda': {'general': 4, 'anime': 6, 'fast': 10},
        'mps': {'general': 2, 'anime': 3, 'fast': 5},
        'cpu': {'general': 0.1, 'anime': 0.15, 'fast': 0.3},
    }

    est_fps = base_fps.get(hw_type, base_fps['cpu']).get(model_category, 1)

    # Scale down fps based on output resolution (1080p = 2M pixels as baseline)
    baseline_pixels = 1920 * 1080
    resolution_factor = baseline_pixels / max(output_pixels, 1)
    est_fps = est_fps * min(resolution_factor, 1.0)  # Can't be faster than baseline

    est_seconds = total_frames / max(est_fps, 0.01)

    if est_seconds < 60:
        return f"~{int(est_seconds)} seconds"
    elif est_seconds < 3600:
        return f"~{int(est_seconds / 60)} minutes"
    else:
        return f"~{est_seconds / 3600:.1f} hours"


# ============================================================================
# FFMPEG FAST UPSCALE (No AI)
# ============================================================================

def upscale_ffmpeg(file_path, scale_factor=2, algorithm='lanczos', output_path=None):
    """
    Fast upscaling using FFmpeg's built-in algorithms.
    No AI, but very fast and good for basic upscaling.
    """
    if not validate_input_file(file_path):
        press_continue()
        return

    video_info = _get_video_info(file_path)
    if not video_info:
        press_continue()
        return

    output_w = video_info['width'] * scale_factor
    output_h = video_info['height'] * scale_factor

    console.print(f"[dim]Input: {video_info['width']}x{video_info['height']}[/dim]")
    console.print(f"[bold cyan]Output: {output_w}x{output_h} (using {algorithm})[/bold cyan]")

    # Output path
    if output_path:
        final_output = output_path
    else:
        suffix = f"upscaled_{scale_factor}x_{algorithm}"
        output_file = f"{Path(file_path).stem}_{suffix}.mp4"
        action_result, final_output = check_output_file(output_file, "Output file")
        if action_result == 'cancel':
            return

    # Get encoding settings
    settings = Settings()
    enc_args = settings.get_encoding_args(quality="high", crf=18)

    console.print("[cyan]Upscaling with FFmpeg...[/cyan]")

    try:
        # Build FFmpeg command
        stream = ffmpeg.input(file_path)

        # Scale filter with chosen algorithm
        stream = ffmpeg.filter(stream, 'scale', output_w, output_h, flags=algorithm)

        # Output with encoding settings
        output_args = {
            'pix_fmt': 'yuv420p',
            **enc_args
        }

        stream = ffmpeg.output(stream, final_output, **output_args)
        stream = ffmpeg.overwrite_output(stream)

        # Run with progress
        ffmpeg.run(stream, quiet=True)

        console.print(f"[bold green]Upscaling complete: {final_output}[/bold green]")

    except ffmpeg.Error as e:
        console.print(f"[bold red]FFmpeg error: {e.stderr.decode() if e.stderr else e}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
    finally:
        press_continue()


# ============================================================================
# AI UPSCALE (Real-ESRGAN)
# ============================================================================

def upscale_video(file_path, scale_factor=None, model_type=None, output_path=None,
                  tile_size=None, denoise_strength=None, fast_mode=False):
    """
    Upscale video using Real-ESRGAN (Super Resolution).

    Args:
        file_path: Input video path
        scale_factor: '2x' or '4x' (or int 2/4)
        model_type: Model name from MODEL_INFO
        output_path: Output file path (optional)
        tile_size: Tile size for memory management (0 = no tiling)
        denoise_strength: 0-1 denoise amount (only for supported models)
        fast_mode: Skip some quality options for speed
    """
    # Check dependencies
    try:
        _apply_torchvision_patch()
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
        from realesrgan.archs.srvgg_arch import SRVGGNetCompact
        import cv2
        import torch
    except ImportError as e:
        console.print(f"[bold red]Missing AI dependencies: {e}[/bold red]")
        console.print("\n[yellow]Install with:[/yellow]")
        console.print("  pip install realesrgan basicsr torch torchvision")
        console.print("\n[dim]For NVIDIA GPU (CUDA 12.1):[/dim]")
        console.print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
        press_continue()
        return

    if not validate_input_file(file_path):
        press_continue()
        return

    # --- Hardware Detection ---
    hw_info = _detect_hardware()
    if not hw_info:
        console.print("[bold red]Failed to initialize PyTorch[/bold red]")
        press_continue()
        return

    device = hw_info['device']

    # Display hardware info
    hw_table = Table(show_header=False, box=None, padding=(0, 1))
    hw_table.add_column(style="cyan")
    hw_table.add_column()

    if hw_info['type'] == 'cuda':
        hw_table.add_row("GPU:", f"[green]{hw_info['name']}[/green]")
        hw_table.add_row("VRAM:", f"[green]{hw_info['vram_gb']:.1f} GB[/green]")
    elif hw_info['type'] == 'mps':
        hw_table.add_row("GPU:", "[green]Apple Silicon (MPS)[/green]")
    else:
        hw_table.add_row("GPU:", "[yellow]None (CPU mode - slow!)[/yellow]")

    console.print(Panel(hw_table, title="Hardware", border_style="cyan"))

    # --- Video Info ---
    video_info = _get_video_info(file_path)
    if not video_info:
        press_continue()
        return

    width, height = video_info['width'], video_info['height']
    fps = video_info['fps']
    total_frames = video_info['total_frames']
    duration = video_info['duration']

    info_table = Table(show_header=False, box=None, padding=(0, 1))
    info_table.add_column(style="dim")
    info_table.add_column()
    info_table.add_row("Resolution:", f"{width}x{height}")
    info_table.add_row("Frame Rate:", f"{fps:.2f} fps")
    info_table.add_row("Duration:", format_duration(duration))
    info_table.add_row("Frames:", f"{total_frames:,}")
    console.print(Panel(info_table, title="Input Video", border_style="blue"))

    # --- Interactive Options (if not preset) ---

    # Upscale mode selection
    if scale_factor is None and model_type is None and not fast_mode:
        mode_choice = questionary.select(
            "Upscale Mode:",
            choices=[
                "🚀 Quick (FFmpeg - No AI, very fast)",
                "⚡ Fast AI (Compact models)",
                "🎨 Quality AI (Best results, slower)",
                "🎌 Anime AI (Optimized for animation)",
                "← Back"
            ]
        ).ask()

        if mode_choice is None or "Back" in mode_choice:
            return

        if "Quick" in mode_choice:
            # Redirect to FFmpeg upscale
            algo = questionary.select(
                "Algorithm:",
                choices=[
                    "lanczos (Sharp - Recommended)",
                    "bicubic (Balanced)",
                    "bilinear (Smooth)",
                    "spline (Very smooth)",
                ]
            ).ask()
            if algo is None:
                return
            algo = algo.split(" ")[0]

            scale = questionary.select("Scale:", choices=["2x", "3x", "4x"]).ask()
            if scale is None:
                return
            scale = int(scale.replace('x', ''))

            return upscale_ffmpeg(file_path, scale_factor=scale, algorithm=algo, output_path=output_path)

        elif "Fast AI" in mode_choice:
            # Ask for scale first to recommend appropriate model
            scale_choice = questionary.select(
                "Output Scale:",
                choices=["2x (Recommended for speed)", "4x"]
            ).ask()
            if scale_choice is None:
                return

            if "2x" in scale_choice:
                model_type = questionary.select(
                    "Fast 2x Model:",
                    choices=[
                        "RealESRGAN_x2plus (Native 2x - Fastest for 2x)",
                        "realesr-general-x4v3 (4x model, output 2x)",
                    ]
                ).ask()
                scale_factor = "2x"
            else:
                model_type = questionary.select(
                    "Fast 4x Model:",
                    choices=[
                        "realesr-general-x4v3 (General purpose - Fast)",
                        "realesr-general-wdn-x4v3 (General + Denoise)",
                        "realesr-animevideov3 (Anime - Fast)",
                    ]
                ).ask()
                scale_factor = "4x"
        elif "Quality" in mode_choice:
            model_type = questionary.select(
                "Quality Model:",
                choices=[
                    "RealESRGAN_x4plus (Best quality)",
                    "RealESRGAN_x2plus (2x - Good for 1080p→4K)",
                    "RealESRNet_x4plus (Balanced)",
                ]
            ).ask()
        elif "Anime" in mode_choice:
            model_type = questionary.select(
                "Anime Model:",
                choices=[
                    "realesr-animevideov3 (Fast video)",
                    "RealESRGAN_x4plus_anime_6B (High quality)",
                ]
            ).ask()

        if model_type is None:
            return

    # Parse model name
    if model_type:
        model_name = model_type.split(" ")[0]
    else:
        model_name = "realesr-general-x4v3"  # Default fast model

    model_info = MODEL_INFO.get(model_name)
    if not model_info:
        console.print(f"[bold red]Unknown model: {model_name}[/bold red]")
        press_continue()
        return

    netscale = model_info['scale']

    # Scale factor
    if scale_factor is None:
        if netscale == 2:
            scale = 2
        else:
            scale_choice = questionary.select(
                "Output Scale:",
                choices=["2x", "4x"]
            ).ask()
            if scale_choice is None:
                return
            scale = int(scale_choice.replace('x', ''))
    else:
        scale = int(str(scale_factor).replace('x', ''))

    # Calculate output resolution
    output_w = width * scale
    output_h = height * scale

    # Warnings for large outputs
    console.print(f"\n[bold cyan]Target: {output_w}x{output_h}[/bold cyan]")

    if output_w > 3840:
        console.print("[yellow]⚠ Output exceeds 4K - this will be slow and use lots of memory[/yellow]")
    if output_w > 7680:
        console.print("[bold red]⚠ Output exceeds 8K - may crash or take hours![/bold red]")

    # Estimate time
    output_pixels = output_w * output_h
    est_time = _estimate_processing_time(total_frames, fps, hw_info['type'], model_info['category'], output_pixels)
    console.print(f"[dim]Estimated time: {est_time}[/dim]")

    # Tile size selection (memory management)
    if tile_size is None and not fast_mode:
        # Smart defaults based on hardware
        if hw_info['type'] == 'cuda' and hw_info['vram_gb']:
            if hw_info['vram_gb'] >= 8:
                default_tile = "Auto (Recommended)"
            else:
                default_tile = "Low Memory (256 tiles)"
        elif hw_info['type'] == 'mps':
            default_tile = "Balanced (512 tiles)"
        else:
            default_tile = "Low Memory (256 tiles)"

        tile_choice = questionary.select(
            "Memory Usage:",
            choices=[
                "Auto (Recommended)",
                "High VRAM (No tiling - fastest if enough memory)",
                "Balanced (512 tiles)",
                "Low Memory (256 tiles)",
                "Very Low (128 tiles - slowest)",
            ],
            default=default_tile
        ).ask()

        if tile_choice is None:
            return

        if "No tiling" in tile_choice:
            tile_size = 0
        elif "128" in tile_choice:
            tile_size = 128
        elif "256" in tile_choice:
            tile_size = 256
        elif "512" in tile_choice:
            tile_size = 512
        else:  # Auto - smart defaults based on output size and hardware
            if hw_info['type'] == 'cuda':
                # CUDA: No tiling for <4K output if enough VRAM
                if hw_info['vram_gb'] and hw_info['vram_gb'] >= 8 and output_w <= 3840:
                    tile_size = 0
                elif hw_info['vram_gb'] and hw_info['vram_gb'] >= 6:
                    tile_size = 512
                else:
                    tile_size = 256
            elif hw_info['type'] == 'mps':
                # MPS: No tiling for <=4K output (unified memory handles it well)
                if output_w <= 3840:
                    tile_size = 0  # No tiling is faster for MPS with unified memory
                else:
                    tile_size = 512
            else:
                tile_size = 256
    else:
        tile_size = tile_size if tile_size is not None else 0

    # MPS optimization: disable half precision (often slower due to conversion overhead)
    use_half = hw_info['half_precision']
    if hw_info['type'] == 'mps':
        use_half = False  # FP32 is often faster on MPS

    if tile_size == 0:
        console.print("[dim]Using no tiling (fastest for your output size)[/dim]")
    else:
        console.print(f"[dim]Using tile size: {tile_size}[/dim]")

    # --- Output Path ---
    if output_path:
        final_output = output_path
    else:
        suffix = f"upscaled_{scale}x_{model_name}"
        output_file = f"{Path(file_path).stem}_{suffix}.mp4"
        action_result, final_output = check_output_file(output_file, "Output file")
        if action_result == 'cancel':
            return

    # --- Initialize Model ---
    console.print("\n[cyan]Loading AI model...[/cyan]")

    try:
        upsampler = _create_upsampler(
            model_name,
            device,
            tile_size,
            half_precision=use_half
        )
        if not upsampler:
            press_continue()
            return
    except Exception as e:
        console.print(f"[bold red]Failed to initialize model: {e}[/bold red]")
        press_continue()
        return

    console.print("[green]Model loaded![/green]")

    # --- Process Video ---
    temp_dir = tempfile.mkdtemp(prefix="peg_upscale_")
    temp_video = os.path.join(temp_dir, "temp_video.mp4")

    try:
        import cv2

        # Input process: decode video to raw frames (BGR for OpenCV compatibility)
        process_in = (
            ffmpeg
            .input(file_path)
            .output('pipe:', format='rawvideo', pix_fmt='bgr24')
            .run_async(pipe_stdout=True, pipe_stderr=True)
        )

        # Output process: encode upscaled frames
        # Use rgb24 for output since we'll convert BGR->RGB before writing
        settings = Settings()
        enc_args = settings.get_encoding_args(quality="high", crf=18)

        process_out = (
            ffmpeg
            .input('pipe:', format='rawvideo', pix_fmt='rgb24', s=f'{output_w}x{output_h}', r=fps)
            .output(temp_video, pix_fmt='yuv420p', **enc_args)
            .overwrite_output()
            .run_async(pipe_stdin=True, pipe_stderr=True)
        )

        console.print(f"\n[bold cyan]Upscaling to {output_w}x{output_h}...[/bold cyan]\n")

        frame_size_in = width * height * 3
        processed = 0
        errors = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=console,
            refresh_per_second=2,
        ) as progress:
            task = progress.add_task(f"Processing frames...", total=total_frames)

            while True:
                # Check if output process is still running
                if process_out.poll() is not None:
                    stderr_out = process_out.stderr.read().decode() if process_out.stderr else ""
                    console.print(f"\n[bold red]FFmpeg encoder crashed![/bold red]")
                    if stderr_out:
                        console.print(f"[dim]{stderr_out[-500:]}[/dim]")  # Last 500 chars
                    break

                in_bytes = process_in.stdout.read(frame_size_in)
                if not in_bytes or len(in_bytes) < frame_size_in:
                    break

                # Decode frame (BGR from ffmpeg)
                frame = np.frombuffer(in_bytes, np.uint8).reshape([height, width, 3])

                # Upscale with Real-ESRGAN (expects BGR, outputs BGR)
                try:
                    output_frame, _ = upsampler.enhance(frame, outscale=scale)
                except RuntimeError as e:
                    error_str = str(e)
                    if 'out of memory' in error_str.lower():
                        console.print("\n[bold red]GPU Out of Memory![/bold red]")
                        console.print("[yellow]Try: Lower tile size, or use a faster model[/yellow]")
                        break
                    errors += 1
                    if errors > 10:
                        console.print(f"\n[bold red]Too many errors, stopping: {e}[/bold red]")
                        break
                    continue

                # Convert BGR -> RGB for ffmpeg output
                output_frame = cv2.cvtColor(output_frame, cv2.COLOR_BGR2RGB)

                # Write to output
                try:
                    process_out.stdin.write(output_frame.astype(np.uint8).tobytes())
                except BrokenPipeError:
                    stderr_out = process_out.stderr.read().decode() if process_out.stderr else ""
                    console.print(f"\n[bold red]FFmpeg pipe broken![/bold red]")
                    if stderr_out:
                        console.print(f"[dim]{stderr_out[-500:]}[/dim]")
                    break

                processed += 1
                progress.update(task, completed=processed)

        # Close pipes
        process_in.stdout.close()
        process_in.wait()
        process_out.stdin.close()
        process_out.wait()

        if processed == 0:
            console.print("[bold red]No frames were processed![/bold red]")
            press_continue()
            return

        # Merge audio
        console.print("\n[cyan]Merging audio...[/cyan]")

        if has_audio_stream(file_path):
            # Mux video with original audio
            (
                ffmpeg
                .output(
                    ffmpeg.input(temp_video),
                    ffmpeg.input(file_path).audio,
                    final_output,
                    c='copy',
                    map_metadata=0,
                    movflags='+faststart'
                )
                .overwrite_output()
                .run(quiet=True)
            )
        else:
            shutil.move(temp_video, final_output)

        # Success
        console.print(f"\n[bold green]✓ Upscaling complete![/bold green]")
        console.print(f"[green]Output: {final_output}[/green]")
        console.print(f"[dim]Processed {processed:,} frames[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Error during upscaling: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
    finally:
        # Cleanup
        try:
            if 'process_in' in locals():
                process_in.stdout.close()
                process_in.kill()
            if 'process_out' in locals():
                process_out.stdin.close()
                process_out.kill()
        except:
            pass

        # Remove temp directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

        # Clear GPU memory
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except:
            pass

        press_continue()


# ============================================================================
# QUICK ENTRY POINTS
# ============================================================================

def upscale_video_fast(file_path, output_path=None):
    """Quick upscale with fast defaults (for GUI/programmatic use)."""
    return upscale_video(
        file_path,
        scale_factor=2,
        model_type="realesr-general-x4v3",
        output_path=output_path,
        tile_size=512,
        fast_mode=True
    )


def upscale_video_quality(file_path, output_path=None):
    """Quality upscale with best defaults."""
    return upscale_video(
        file_path,
        scale_factor=4,
        model_type="RealESRGAN_x4plus",
        output_path=output_path,
        tile_size=512,
        fast_mode=True
    )
