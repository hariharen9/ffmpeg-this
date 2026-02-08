"""
AI Auto-Dubbing Feature
Pipeline: Whisper (transcribe) → Deep Translator (translate) → Piper TTS (synthesize) → FFmpeg (merge)
"""

import os
import sys
import shutil
import tempfile
import subprocess
import logging
import wave
import struct
from pathlib import Path
from typing import Optional, Callable, List, Dict, Tuple

import numpy as np
import ffmpeg
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

from peg_this.utils.ffmpeg_utils import has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, check_disk_space,
    get_video_duration, format_duration, press_continue
)

console = Console()
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Directory to store downloaded Piper models
MODEL_CACHE_DIR = Path.home() / ".peg_this" / "models" / "piper"
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Language Configuration
# Format: "Display Name": {
#     "code": Deep Translator language code,
#     "voices": [(voice_model_name, gender, description), ...]
# }
# Voice models verified from: https://huggingface.co/rhasspy/piper-voices
LANGUAGES = {
    "Spanish": {
        "code": "es",
        "voices": [
            ("es_ES-davefx-medium", "Male", "Dave - Clear"),
            ("es_ES-carlfm-x_low", "Male", "Carl - Fast"),
            ("es_MX-claude-high", "Male", "Claude - Mexican"),
        ]
    },
    "French": {
        "code": "fr",
        "voices": [
            ("fr_FR-siwis-medium", "Female", "Siwis - Clear"),
            ("fr_FR-gilles-low", "Male", "Gilles - Fast"),
            ("fr_FR-mls-medium", "Male", "MLS - Natural"),
        ]
    },
    "German": {
        "code": "de",
        "voices": [
            ("de_DE-thorsten-high", "Male", "Thorsten - High Quality"),
            ("de_DE-thorsten-medium", "Male", "Thorsten - Medium"),
            ("de_DE-eva_k-x_low", "Female", "Eva - Fast"),
            ("de_DE-kerstin-low", "Female", "Kerstin - Natural"),
        ]
    },
    "Italian": {
        "code": "it",
        "voices": [
            ("it_IT-paola-medium", "Female", "Paola - Natural"),
            ("it_IT-riccardo-x_low", "Male", "Riccardo - Fast"),
        ]
    },
    "Portuguese": {
        "code": "pt",
        "voices": [
            ("pt_BR-faber-medium", "Male", "Faber - Brazilian"),
            ("pt_BR-edresson-low", "Male", "Edresson - Fast"),
        ]
    },
    "Russian": {
        "code": "ru",
        "voices": [
            ("ru_RU-irina-medium", "Female", "Irina - Natural"),
            ("ru_RU-denis-medium", "Male", "Denis - Clear"),
            ("ru_RU-ruslan-medium", "Male", "Ruslan - Deep"),
        ]
    },
    "Chinese": {
        "code": "zh-CN",
        "voices": [
            ("zh_CN-huayan-medium", "Female", "Huayan - Standard"),
            ("zh_CN-huayan-x_low", "Female", "Huayan - Fast"),
        ]
    },
    "Hindi": {
        "code": "hi",
        "voices": [
            ("hi_IN-rohan-medium", "Male", "Rohan - Clear"),
            ("hi_IN-pratham-medium", "Male", "Pratham - Natural"),
            ("hi_IN-priyamvada-medium", "Female", "Priyamvada - Female"),
        ]
    },
    "Polish": {
        "code": "pl",
        "voices": [
            ("pl_PL-gosia-medium", "Female", "Gosia - Natural"),
            ("pl_PL-darkman-medium", "Male", "Darkman - Clear"),
            ("pl_PL-mc_speech-medium", "Male", "MC Speech - Deep"),
        ]
    },
    "Dutch": {
        "code": "nl",
        "voices": [
            ("nl_NL-mls-medium", "Male", "MLS - Standard"),
            ("nl_BE-nathalie-medium", "Female", "Nathalie - Belgian"),
        ]
    },
    "Turkish": {
        "code": "tr",
        "voices": [
            ("tr_TR-dfki-medium", "Male", "DFKI - Standard"),
        ]
    },
    "Vietnamese": {
        "code": "vi",
        "voices": [
            ("vi_VN-vais1000-medium", "Female", "VAIS - Natural"),
            ("vi_VN-vivos-x_low", "Female", "ViVOS - Fast"),
        ]
    },
    "Ukrainian": {
        "code": "uk",
        "voices": [
            ("uk_UA-ukrainian_tts-medium", "Female", "Ukrainian TTS"),
            ("uk_UA-lada-x_low", "Female", "Lada - Fast"),
        ]
    },
    "Greek": {
        "code": "el",
        "voices": [
            ("el_GR-rapunzelina-medium", "Female", "Rapunzelina - Clear"),
        ]
    },
    "Czech": {
        "code": "cs",
        "voices": [
            ("cs_CZ-jirka-medium", "Male", "Jirka - Natural"),
        ]
    },
    "Swedish": {
        "code": "sv",
        "voices": [
            ("sv_SE-nst-medium", "Male", "NST - Standard"),
            ("sv_SE-lisa-medium", "Female", "Lisa - Natural"),
        ]
    },
    "Danish": {
        "code": "da",
        "voices": [
            ("da_DK-talesyntese-medium", "Male", "Talesyntese - Clear"),
        ]
    },
    "Finnish": {
        "code": "fi",
        "voices": [
            ("fi_FI-harri-medium", "Male", "Harri - Natural"),
        ]
    },
    "Norwegian": {
        "code": "no",
        "voices": [
            ("no_NO-talesyntese-medium", "Male", "Talesyntese - Standard"),
        ]
    },
    "Arabic": {
        "code": "ar",
        "voices": [
            ("ar_JO-kareem-medium", "Male", "Kareem - Jordanian"),
        ]
    },
    "Catalan": {
        "code": "ca",
        "voices": [
            ("ca_ES-upc_ona-medium", "Female", "Ona - Clear"),
        ]
    },
}


# ============================================================================
# HARDWARE DETECTION
# ============================================================================

def detect_compute_device():
    """Detect best available compute device for Whisper."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda", "float16"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            # MPS works but int8 is more stable
            return "cpu", "int8"  # MPS has issues with whisper, use CPU
        else:
            return "cpu", "int8"
    except ImportError:
        return "cpu", "int8"


# ============================================================================
# DEPENDENCY CHECKING
# ============================================================================

def check_dependencies() -> Tuple[bool, List[str]]:
    """Check if required libraries are installed. Returns (all_ok, missing_list)."""
    missing = []

    # Check faster-whisper
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        missing.append("faster-whisper")

    # Check deep-translator
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        missing.append("deep-translator")

    # Check piper-tts
    try:
        from piper import PiperVoice
    except ImportError:
        missing.append("piper-tts")

    # Check pydub
    try:
        from pydub import AudioSegment
    except ImportError:
        missing.append("pydub")

    # Check onnxruntime (needed for piper)
    try:
        import onnxruntime
    except ImportError:
        missing.append("onnxruntime")

    return len(missing) == 0, missing


def show_dependency_help(missing: List[str]):
    """Display helpful installation instructions."""
    console.print("\n[bold red]Missing dependencies for Auto-Dubbing:[/bold red]")
    for m in missing:
        console.print(f"  [red]✗[/red] {m}")

    console.print("\n[yellow]To install, run:[/yellow]")
    console.print("[bold]pip install faster-whisper deep-translator piper-tts pydub onnxruntime[/bold]")

    console.print("\n[dim]Note: First run will download AI models (Whisper ~150MB, Voice ~50MB each)[/dim]")


# ============================================================================
# MODEL MANAGEMENT
# ============================================================================

def get_piper_model_urls(model_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Construct Hugging Face URLs for a Piper voice model.
    Returns (onnx_url, json_url) or (None, None) if invalid.
    """
    # Parse model name: es_ES-davefx-medium -> (es, es_ES, davefx, medium)
    parts = model_name.split('-')
    if len(parts) < 3:
        return None, None

    region_code = parts[0]  # es_ES
    quality = parts[-1]      # medium
    name = "-".join(parts[1:-1])  # davefx (handles multi-part names)

    lang_code = region_code.split('_')[0]  # es

    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    url_path = f"{lang_code}/{region_code}/{name}/{quality}/{model_name}"

    return f"{base_url}/{url_path}.onnx", f"{base_url}/{url_path}.onnx.json"


def download_with_progress(url: str, dest_path: Path, description: str = "Downloading") -> bool:
    """Download a file with a progress bar."""
    import requests

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(description, total=total_size)

            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))

        return True

    except Exception as e:
        logger.error(f"Download failed: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def ensure_voice_model(model_name: str, log_func: Callable = None) -> Optional[Path]:
    """
    Ensure a Piper voice model is available locally.
    Downloads from Hugging Face if not present.
    Returns path to .onnx file or None on failure.
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            console.print(f"[dim]{msg}[/dim]")

    onnx_path = MODEL_CACHE_DIR / f"{model_name}.onnx"
    json_path = MODEL_CACHE_DIR / f"{model_name}.onnx.json"

    # Check if already cached
    if onnx_path.exists() and json_path.exists():
        return onnx_path

    log(f"Downloading voice model: {model_name}")

    onnx_url, json_url = get_piper_model_urls(model_name)
    if not onnx_url:
        log(f"Error: Invalid model name format: {model_name}")
        return None

    # Download JSON config (small)
    if not download_with_progress(json_url, json_path, "Config"):
        log("Failed to download model config")
        return None

    # Download ONNX model (larger)
    if not download_with_progress(onnx_url, onnx_path, "Voice Model"):
        log("Failed to download voice model")
        json_path.unlink(missing_ok=True)
        return None

    log("Voice model ready!")
    return onnx_path


# ============================================================================
# AUDIO PROCESSING
# ============================================================================

def extract_audio_for_transcription(input_file: str, output_wav: str) -> bool:
    """Extract audio from video as 16kHz mono WAV for Whisper."""
    try:
        (
            ffmpeg
            .input(input_file)
            .output(output_wav, ac=1, ar=16000, vn=None, acodec='pcm_s16le')
            .overwrite_output()
            .run(quiet=True)
        )
        return os.path.exists(output_wav) and os.path.getsize(output_wav) > 0
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}")
        return False


def adjust_audio_speed(audio_segment, target_duration_ms: int):
    """
    Adjust audio speed to fit target duration using pydub.
    Returns adjusted AudioSegment.
    """
    from pydub import AudioSegment
    from pydub.effects import speedup

    current_duration = len(audio_segment)

    if current_duration <= 0 or target_duration_ms <= 0:
        return audio_segment

    ratio = current_duration / target_duration_ms

    # Limit speed adjustment to reasonable range (0.5x to 2.0x)
    ratio = max(0.5, min(2.0, ratio))

    if abs(ratio - 1.0) < 0.05:  # Within 5%, don't adjust
        return audio_segment

    if ratio > 1.0:
        # Need to speed up (make shorter)
        # pydub speedup only works for >1.0
        try:
            # Use frame rate manipulation for speed change
            new_frame_rate = int(audio_segment.frame_rate * ratio)
            adjusted = audio_segment._spawn(audio_segment.raw_data, overrides={
                "frame_rate": new_frame_rate
            }).set_frame_rate(audio_segment.frame_rate)
            return adjusted
        except:
            return audio_segment
    else:
        # Need to slow down (make longer)
        try:
            new_frame_rate = int(audio_segment.frame_rate * ratio)
            adjusted = audio_segment._spawn(audio_segment.raw_data, overrides={
                "frame_rate": new_frame_rate
            }).set_frame_rate(audio_segment.frame_rate)
            return adjusted
        except:
            return audio_segment


def synthesize_speech(text: str, model_path: Path, output_wav: str) -> bool:
    """
    Synthesize speech using Piper TTS.
    Returns True on success.
    """
    try:
        from piper import PiperVoice

        # Load voice model
        voice = PiperVoice.load(str(model_path))

        # Get sample rate from voice config
        sample_rate = voice.config.sample_rate

        # Synthesize to WAV - must configure wave params first
        with wave.open(output_wav, 'wb') as wav_file:
            wav_file.setnchannels(1)       # Mono
            wav_file.setsampwidth(2)       # 16-bit (2 bytes)
            wav_file.setframerate(sample_rate)
            voice.synthesize(text, wav_file)

        return os.path.exists(output_wav) and os.path.getsize(output_wav) > 0

    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        return False


# ============================================================================
# TRANSLATION
# ============================================================================

def translate_segments(segments: List[Dict], source_lang: str, target_lang: str,
                       log_func: Callable = None) -> List[Dict]:
    """
    Translate a list of segments using Google Translate.
    Handles rate limiting and batching.
    """
    from deep_translator import GoogleTranslator

    def log(msg):
        if log_func:
            log_func(msg)

    translator = GoogleTranslator(source=source_lang, target=target_lang)
    translated = []

    # Batch translations to avoid rate limiting (max 5000 chars per request)
    batch_texts = []
    batch_indices = []
    current_batch_len = 0

    for i, seg in enumerate(segments):
        text = seg.get('text', '').strip()
        if not text:
            continue

        # Check if adding this would exceed batch limit
        if current_batch_len + len(text) > 4500 and batch_texts:
            # Translate current batch
            try:
                batch_result = translator.translate_batch(batch_texts)
                for idx, trans_text in zip(batch_indices, batch_result):
                    segments[idx]['translated'] = trans_text
            except Exception as e:
                log(f"Batch translation error: {e}")
                # Fall back to individual translation
                for idx, orig_text in zip(batch_indices, batch_texts):
                    try:
                        segments[idx]['translated'] = translator.translate(orig_text)
                    except:
                        segments[idx]['translated'] = orig_text

            batch_texts = []
            batch_indices = []
            current_batch_len = 0

        batch_texts.append(text)
        batch_indices.append(i)
        current_batch_len += len(text)

    # Translate remaining batch
    if batch_texts:
        try:
            batch_result = translator.translate_batch(batch_texts)
            for idx, trans_text in zip(batch_indices, batch_result):
                segments[idx]['translated'] = trans_text
        except Exception as e:
            log(f"Final batch translation error: {e}")
            for idx, orig_text in zip(batch_indices, batch_texts):
                try:
                    segments[idx]['translated'] = translator.translate(orig_text)
                except:
                    segments[idx]['translated'] = orig_text

    return segments


# ============================================================================
# MAIN DUBBING PIPELINE
# ============================================================================

def run_dubbing_pipeline(
    input_file: str,
    output_path: str,
    target_lang: str,
    voice_model: str,
    whisper_model: str = "base",
    original_volume: float = 0.1,
    progress_callback: Callable = None,
    log_callback: Callable = None
) -> bool:
    """
    Main dubbing pipeline.

    Args:
        input_file: Path to input video
        output_path: Path for output video
        target_lang: Target language name (e.g., "Spanish")
        voice_model: Piper voice model name
        whisper_model: Whisper model size (tiny/base/small/medium)
        original_volume: Volume of original audio (0.0 to 1.0)
        progress_callback: Function to report progress (0.0 to 1.0)
        log_callback: Function to log messages

    Returns:
        True on success, False on failure
    """
    from pydub import AudioSegment

    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            console.print(f"[cyan]{msg}[/cyan]")

    def progress(p):
        if progress_callback:
            progress_callback(p)

    # Validate language
    if target_lang not in LANGUAGES:
        log(f"Error: Unsupported language '{target_lang}'")
        return False

    lang_config = LANGUAGES[target_lang]
    target_code = lang_config["code"]

    # Ensure voice model is available
    log("Checking voice model...")
    model_path = ensure_voice_model(voice_model, log)
    if not model_path:
        log("Error: Could not load voice model")
        return False

    progress(0.05)

    # Create temp directory for intermediate files
    with tempfile.TemporaryDirectory(prefix="peg_dub_") as temp_dir:
        temp_dir = Path(temp_dir)

        # Step 1: Extract audio
        log("Extracting audio...")
        audio_wav = temp_dir / "audio.wav"
        if not extract_audio_for_transcription(input_file, str(audio_wav)):
            log("Error: Failed to extract audio")
            return False

        progress(0.1)

        # Step 2: Transcribe with Whisper
        log(f"Transcribing with Whisper ({whisper_model})...")
        try:
            from faster_whisper import WhisperModel

            device, compute_type = detect_compute_device()
            log(f"Using device: {device}")

            model = WhisperModel(whisper_model, device=device, compute_type=compute_type)

            segments_gen, info = model.transcribe(
                str(audio_wav),
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300)
            )

            # Convert generator to list with timing info
            segments = []
            for seg in segments_gen:
                segments.append({
                    'start': seg.start,
                    'end': seg.end,
                    'text': seg.text.strip(),
                    'duration': seg.end - seg.start
                })

            source_lang = info.language
            log(f"Detected source language: {source_lang}")
            log(f"Found {len(segments)} speech segments")

            if not segments:
                log("Error: No speech detected in video")
                return False

        except Exception as e:
            log(f"Error during transcription: {e}")
            return False

        progress(0.3)

        # Step 3: Translate
        log(f"Translating to {target_lang}...")
        try:
            segments = translate_segments(segments, source_lang, target_code, log)

            # Count successful translations
            translated_count = sum(1 for s in segments if s.get('translated'))
            log(f"Translated {translated_count}/{len(segments)} segments")

        except Exception as e:
            log(f"Error during translation: {e}")
            return False

        progress(0.4)

        # Step 4: Synthesize speech for each segment
        log("Synthesizing dubbed audio...")
        tts_segments = []

        for i, seg in enumerate(segments):
            translated_text = seg.get('translated', '')
            if not translated_text:
                continue

            seg_wav = temp_dir / f"seg_{i:04d}.wav"

            try:
                if synthesize_speech(translated_text, model_path, str(seg_wav)):
                    tts_segments.append({
                        'start': seg['start'],
                        'end': seg['end'],
                        'duration': seg['duration'],
                        'wav': seg_wav
                    })
            except Exception as e:
                log(f"Warning: Failed to synthesize segment {i}: {e}")

            # Update progress (40% to 70%)
            progress(0.4 + (i / len(segments)) * 0.3)

        log(f"Synthesized {len(tts_segments)}/{len(segments)} segments")

        if not tts_segments:
            log("Error: No audio segments were synthesized")
            return False

        progress(0.7)

        # Step 5: Mix audio track
        log("Building dubbed audio track...")
        try:
            video_duration = get_video_duration(input_file)
            video_duration_ms = int(video_duration * 1000)

            # Create silent base track at 22050Hz (Piper's native rate)
            dubbed_track = AudioSegment.silent(duration=video_duration_ms, frame_rate=22050)

            for seg in tts_segments:
                try:
                    seg_audio = AudioSegment.from_wav(str(seg['wav']))

                    # Adjust speed to fit original segment duration
                    target_duration_ms = int(seg['duration'] * 1000)
                    if target_duration_ms > 0:
                        seg_audio = adjust_audio_speed(seg_audio, target_duration_ms)

                    # Overlay at correct position
                    start_ms = int(seg['start'] * 1000)
                    dubbed_track = dubbed_track.overlay(seg_audio, position=start_ms)

                except Exception as e:
                    logger.warning(f"Error mixing segment: {e}")

            # Export dubbed track
            dubbed_wav = temp_dir / "dubbed_full.wav"
            dubbed_track.export(str(dubbed_wav), format="wav")

        except Exception as e:
            log(f"Error building audio track: {e}")
            return False

        progress(0.85)

        # Step 6: Merge with video
        log("Merging audio with video...")
        try:
            input_video = ffmpeg.input(input_file)
            dubbed_audio = ffmpeg.input(str(dubbed_wav))

            if original_volume > 0:
                # Mix original audio (ducked) with dubbed audio
                original_audio = input_video.audio.filter('volume', original_volume)
                mixed_audio = ffmpeg.filter([original_audio, dubbed_audio], 'amix',
                                           inputs=2, duration='first',
                                           weights=f"{original_volume} 1")
            else:
                # Replace audio entirely
                mixed_audio = dubbed_audio

            # Output with video copy and new audio
            output = ffmpeg.output(
                input_video.video,
                mixed_audio,
                output_path,
                vcodec='copy',
                acodec='aac',
                audio_bitrate='192k'
            )
            output = output.overwrite_output()

            ffmpeg.run(output, quiet=True)

        except ffmpeg.Error as e:
            stderr = e.stderr.decode() if e.stderr else str(e)
            log(f"Error merging audio: {stderr}")
            return False

        progress(1.0)
        log("Dubbing complete!")
        return True


# ============================================================================
# CLI INTERFACE
# ============================================================================

def auto_dub(file_path: str):
    """Interactive CLI for auto-dubbing a video."""

    # Validate input
    if not validate_input_file(file_path):
        press_continue()
        return

    # Check dependencies
    ok, missing = check_dependencies()
    if not ok:
        show_dependency_help(missing)
        press_continue()
        return

    # Check for audio
    if not has_audio_stream(file_path):
        console.print("[bold red]Error: Video has no audio track to dub.[/bold red]")
        press_continue()
        return

    # Show video info
    duration = get_video_duration(file_path)
    console.print(f"\n[dim]Video duration: {format_duration(duration)}[/dim]")

    if duration > 600:  # 10 minutes
        console.print("[yellow]Note: Long videos may take significant time to process.[/yellow]")

    # Select target language
    lang_choices = list(LANGUAGES.keys()) + ["← Back"]
    target_lang = questionary.select(
        "Select target language:",
        choices=lang_choices
    ).ask()

    if target_lang == "← Back" or target_lang is None:
        return

    # Select voice
    lang_config = LANGUAGES[target_lang]
    voices = lang_config["voices"]

    if len(voices) > 1:
        voice_choices = [f"{v[0]} ({v[1]} - {v[2]})" for v in voices]
        voice_choice = questionary.select(
            "Select voice:",
            choices=voice_choices + ["← Back"]
        ).ask()

        if voice_choice == "← Back" or voice_choice is None:
            return

        voice_model = voice_choice.split(" ")[0]
    else:
        voice_model = voices[0][0]
        console.print(f"[dim]Using voice: {voices[0][2]}[/dim]")

    # Select Whisper model
    whisper_model = questionary.select(
        "Whisper model (accuracy vs speed):",
        choices=[
            "tiny (Fastest, less accurate)",
            "base (Balanced - Recommended)",
            "small (More accurate, slower)",
            "medium (Most accurate, slowest)"
        ],
        default="base (Balanced - Recommended)"
    ).ask()

    if whisper_model is None:
        return

    whisper_model = whisper_model.split(" ")[0]

    # Original audio volume
    volume_choice = questionary.select(
        "Original audio volume:",
        choices=[
            "Mute (0%) - Dubbed audio only",
            "Quiet (10%) - Background ambience",
            "Low (25%) - Audible background",
            "Medium (50%) - Mixed equally"
        ],
        default="Quiet (10%) - Background ambience"
    ).ask()

    if volume_choice is None:
        return

    volume_map = {"Mute": 0.0, "Quiet": 0.1, "Low": 0.25, "Medium": 0.5}
    original_volume = volume_map.get(volume_choice.split(" ")[0], 0.1)

    # Output file
    input_p = Path(file_path)
    lang_suffix = target_lang.lower().replace(" ", "_")
    output_name = f"{input_p.stem}_dubbed_{lang_suffix}{input_p.suffix}"
    output_path = input_p.parent / output_name

    action_result, final_output = check_output_file(str(output_path), "Output video")
    if action_result == 'cancel':
        return

    # Check disk space
    if not check_disk_space(file_path, multiplier=3):
        return

    # Show summary
    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column(style="cyan")
    summary.add_column()
    summary.add_row("Target Language:", target_lang)
    summary.add_row("Voice:", voice_model)
    summary.add_row("Whisper Model:", whisper_model)
    summary.add_row("Original Volume:", f"{int(original_volume * 100)}%")
    summary.add_row("Output:", str(final_output))
    console.print(Panel(summary, title="Dubbing Configuration", border_style="blue"))

    # Confirm
    if not questionary.confirm("Start dubbing?", default=True).ask():
        return

    console.print()

    # Run pipeline
    success = run_dubbing_pipeline(
        input_file=file_path,
        output_path=final_output,
        target_lang=target_lang,
        voice_model=voice_model,
        whisper_model=whisper_model,
        original_volume=original_volume,
        log_callback=lambda msg: console.print(f"[cyan]{msg}[/cyan]")
    )

    if success:
        console.print(f"\n[bold green]✓ Dubbing complete![/bold green]")
        console.print(f"[green]Output: {final_output}[/green]")
    else:
        console.print("\n[bold red]✗ Dubbing failed.[/bold red]")

    press_continue()
