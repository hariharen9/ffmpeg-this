"""AI Auto-Dubbing feature using Whisper, Deep Translator, and Piper TTS."""

import os
import shutil
import tempfile
import subprocess
import logging
import requests
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, DownloadColumn

try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, check_disk_space,
    get_video_duration, format_duration, press_continue
)
from peg_this.features.subtitle import extract_audio_for_whisper

console = Console()
logger = logging.getLogger(__name__)

# Directory to store downloaded Piper models
MODEL_CACHE_DIR = Path.home() / ".peg_this" / "models" / "piper"
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Language mapping for Deep Translator and Piper
# Format: "Friendly Name": (Deep Translator Code, Piper Voice Model Name)
LANGUAGES = {
    "Spanish": ("es", "es_ES-sharvard-medium"),
    "French": ("fr", "fr_FR-siwis-medium"),
    "German": ("de", "de_DE-thorsten-high"),
    "Italian": ("it", "it_IT-paola-medium"),
    "Portuguese": ("pt", "pt_PT-tugao-medium"),
    "Russian": ("ru", "ru_RU-denis-medium"),
    "Chinese": ("zh-CN", "zh_CN-huayan-medium"),
    "Hindi": ("hi", "hi_IN-pratham-medium"),
    "Malayalam": ("ml", "ml_IN-meera-medium"),
    # "Tamil": ("ta", "ta_IN-kanmani-medium"), # Not available in Piper yet
    # "Telugu": ("te", "te_IN-stt-medium"),   # Not available in Piper yet
    # "Kannada": ("kn", "kn_IN-stt-medium"),  # Not available in Piper yet
}

def check_dependencies():
    """Check if required AI libraries are installed."""
    missing = []
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        missing.append("faster-whisper")
    
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        missing.append("deep-translator")
        
    try:
        import pathvalidate
    except ImportError:
        missing.append("pathvalidate")

    try:
        import pydub
    except ImportError:
        missing.append("pydub")

    try:
        subprocess.run(["piper", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        missing.append("piper-tts (CLI 'piper' must be in PATH)")

    if missing:
        console.print("[bold red]Missing dependencies for Auto-Dubbing:[/bold red]")
        for m in missing:
            console.print(f" - {m}")
        console.print("\n[yellow]To install them, run:[/yellow]")
        console.print("pip install faster-whisper deep-translator pathvalidate pydub piper-tts requests")
        return False
    return True

def get_model_url(model_name):
    """Constructs the Hugging Face URL for a given model name."""
    # Pattern: zh_CN-huayan-medium -> zh_CN, huayan, medium
    # But directory structure is usually: /es/es_ES/sharpi/medium/
    
    parts = model_name.split('-')
    if len(parts) < 3:
        return None, None
        
    region_code = parts[0] # es_ES
    quality = parts[-1]    # medium
    name = "-".join(parts[1:-1]) # sharpi (handles multi-word names if any)
    
    lang_code = region_code.split('_')[0] # es
    
    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    
    # URL Construction
    # https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharpi/medium/es_ES-sharpi-medium.onnx
    url_path = f"{lang_code}/{region_code}/{name}/{quality}/{model_name}"
    
    onnx_url = f"{base_url}/{url_path}.onnx"
    json_url = f"{base_url}/{url_path}.onnx.json"
    
    return onnx_url, json_url

def download_file(url, path, progress_callback=None):
    """Download a file with progress."""
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            
            with open(path, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded / total_size)
        return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        if os.path.exists(path):
            os.remove(path)
        return False

def ensure_voice_model(model_name, log_callback=None):
    """
    Checks if model exists in cache. If not, downloads it.
    Returns path to .onnx file or None if failed.
    """
    def log(msg):
        if log_callback: log_callback(msg)
        else: logger.info(msg)

    onnx_path = MODEL_CACHE_DIR / f"{model_name}.onnx"
    json_path = MODEL_CACHE_DIR / f"{model_name}.onnx.json"
    
    if onnx_path.exists() and json_path.exists():
        return str(onnx_path)
        
    log(f"Voice model '{model_name}' not found locally. Downloading...")
    onnx_url, json_url = get_model_url(model_name)
    
    if not onnx_url:
        log(f"Error: Could not determine URL for model {model_name}")
        return None
        
    # Download JSON (small)
    log(f"Downloading config...")
    if not download_file(json_url, json_path):
        log("Failed to download model config.")
        return None
        
    # Download ONNX (large)
    log(f"Downloading model (this may take a moment)...")
    # For TUI we could use a rich progress bar here, but for now a simple wait
    if not download_file(onnx_url, onnx_path):
        log("Failed to download model file.")
        return None
        
    log("Model download complete.")
    return str(onnx_path)

def run_piper(text, output_wav, model_path):
    """Run Piper TTS to generate speech."""
    try:
        cmd = [
            "piper",
            "--model", model_path,
            "--output_file", output_wav
        ]
        # Piper expects input from stdin
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(input=text)
        
        if process.returncode != 0:
            # Filter out common benign warnings if needed, but usually any stderr with nonzero exit is bad
            logger.error(f"Piper error: {stderr}")
            return False
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.error(f"Piper exception: {e}")
        return False

def run_dubbing_pipeline(input_file, output_path, target_lang_name, model_size="base", progress_callback=None, log_callback=None):
    """
    Core pipeline logic for Auto-Dubbing.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            logger.info(msg)

    if target_lang_name not in LANGUAGES:
        log(f"Error: Language {target_lang_name} not supported.")
        return False

    if AudioSegment is None:
        log("Error: pydub is not installed. Please run: pip install pydub")
        return False

    target_code, voice_model_name = LANGUAGES[target_lang_name]
    
    # Ensure Model Exists
    model_path = ensure_voice_model(voice_model_name, log_callback=log)
    if not model_path:
        log("Error: Could not load or download TTS voice model.")
        return False
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Transcribe
            log(f"Extracting audio and transcribing ({model_size})...")
            wav_path = extract_audio_for_whisper(input_file, temp_dir)
            if not wav_path:
                log("Failed to extract audio.")
                return False

            from faster_whisper import WhisperModel
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            # Enable VAD filter to ignore silence and get accurate start times
            segments_generator, info = model.transcribe(
                wav_path, 
                beam_size=5, 
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            segments = list(segments_generator)
            source_code = info.language
            log(f"Detected language: {source_code}")

            if not segments:
                log("No speech detected.")
                return False

            # 2. Setup Translation
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source=source_code, target=target_code)

            # 3. Translate and Synthesize
            log(f"Dubbing to {target_lang_name} (Source: {source_code})...")
            dubbed_segments = []
            total = len(segments)
            
            for i, segment in enumerate(segments):
                try:
                    # Translate
                    translated_text = translator.translate(segment.text)
                    if not translated_text: continue 

                    # Synthesize
                    seg_wav = os.path.join(temp_dir, f"seg_{i}.wav")
                    success = run_piper(translated_text, seg_wav, model_path)
                    
                    if success and os.path.exists(seg_wav):
                        dubbed_segments.append({
                            'start': segment.start,
                            'end': segment.end,
                            'wav': seg_wav
                        })
                    else:
                        log(f"Warning: Failed to synthesize segment {i}")
                except Exception as e:
                    log(f"Error processing segment {i}: {e}")
                
                if progress_callback:
                    progress_callback((i + 1) / total * 0.7) 

            if not dubbed_segments:
                log("Failed to generate any dubbed audio.")
                return False

            # 4. Mix Audio using Pydub
            log("Constructing audio track (44.1kHz)...")
            duration_sec = get_video_duration(input_file)
            
            # Create silence track of full duration with standard sample rate
            full_audio = AudioSegment.silent(duration=int(duration_sec * 1000), frame_rate=44100)
            
            for i, seg in enumerate(dubbed_segments):
                try:
                    seg_audio = AudioSegment.from_wav(seg['wav'])
                    
                    # Log timing for debugging
                    if i < 3: 
                        log(f"Seg {i}: Orig Start {seg['start']:.2f}s -> Placing at {seg['start']:.2f}s")
                        
                    start_ms = int(seg['start'] * 1000)
                    full_audio = full_audio.overlay(seg_audio, position=start_ms)
                except Exception as e:
                    log(f"Error mixing segment: {e}")

            mixed_wav_path = os.path.join(temp_dir, "dubbed_track.wav")
            full_audio.export(mixed_wav_path, format="wav")

            # 5. Merge with Video (preserving original audio at low volume)
            log("Merging with video...")
            input_video = ffmpeg.input(input_file)
            original_audio = input_video.audio.filter('volume', 0.1)
            new_dub_audio = ffmpeg.input(mixed_wav_path)
            
            final_audio = ffmpeg.filter([original_audio, new_dub_audio], 'amix', inputs=2, duration='first')
            
            # Use vcodec copy if possible
            stream = ffmpeg.output(input_video.video, final_audio, output_path, vcodec='copy', acodec='aac')
            stream = stream.overwrite_output()
            
            if run_command(stream, description="Finalizing Dub", show_progress=False):
                if progress_callback: progress_callback(1.0)
                return True
            else:
                log("FFmpeg merge failed.")
                return False

    except Exception as e:
        log(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def auto_dub(file_path):
    """CLI Wrapper for Auto Dubbing."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_dependencies():
        press_continue()
        return

    if not has_audio_stream(file_path):
        console.print("[bold red]Error: File has no audio stream to dub.[/bold red]")
        press_continue()
        return

    duration = get_video_duration(file_path)
    console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

    # Select Target Language
    target_lang = questionary.select(
        "Select target language for dubbing:",
        choices=list(LANGUAGES.keys()) + ["← Back"]
    ).ask()

    if target_lang == "← Back" or target_lang is None:
        return

    # Output file
    input_p = Path(file_path)
    output_path = input_p.with_name(f"{input_p.stem}_dubbed_{target_lang.lower()}{input_p.suffix}")
    action_result, final_output = check_output_file(str(output_path), "Video file")

    if action_result == 'cancel':
        return

    if not check_disk_space(file_path, multiplier=2):
        return

    def cli_progress(p):
        pass 

    def cli_log(msg):
        console.print(f"[cyan]{msg}[/cyan]")

    with console.status("[bold green]Processing Auto-Dubbing...[/bold green]"):
        success = run_dubbing_pipeline(
            file_path, 
            final_output, 
            target_lang, 
            model_size="base",
            progress_callback=cli_progress,
            log_callback=cli_log
        )

    if success:
        console.print(f"[bold green]Success! Saved to: {final_output}[/bold green]")
    else:
        console.print("[bold red]Dubbing Failed.[/bold red]")
    
    press_continue()
