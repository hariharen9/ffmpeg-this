import os
import tempfile
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream

console = Console()

WHISPER_MODELS = [
    "tiny", "tiny.en", "base", "base.en", "small", "small.en",
    "medium", "medium.en", "large-v2", "large-v3",
]


def check_existing_subtitles(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        subtitle_streams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'subtitle']
        return len(subtitle_streams) > 0, len(subtitle_streams)
    except Exception:
        return False, 0


def get_video_duration(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        return float(probe['format'].get('duration', 0))
    except Exception:
        return 0


def check_output_file(output_path, file_type="file"):
    if not os.path.exists(output_path):
        return 'proceed', output_path

    console.print(f"[yellow]Warning: {file_type} already exists:[/yellow]")
    console.print(f"[dim]{output_path}[/dim]")

    choice = questionary.select(
        "What would you like to do?",
        choices=["Overwrite existing file", "Save with a new name", "Cancel operation"]
    ).ask()

    if not choice or "Cancel" in choice:
        return 'cancel', None
    elif "Overwrite" in choice:
        return 'overwrite', output_path
    else:
        path = Path(output_path)
        counter = 1
        while True:
            new_name = f"{path.stem}_{counter}{path.suffix}"
            new_path = path.with_name(new_name)
            if not os.path.exists(new_path):
                console.print(f"[cyan]Will save as: {new_path.name}[/cyan]")
                return 'rename', str(new_path)
            counter += 1


def check_disk_space(file_path, multiplier=2):
    try:
        input_size = os.path.getsize(file_path)
        required_space = input_size * multiplier
        import shutil
        total, used, free = shutil.disk_usage(Path(file_path).parent)
        if free < required_space:
            free_gb = free / (1024**3)
            required_gb = required_space / (1024**3)
            console.print(f"[yellow]Warning: Low disk space![/yellow]")
            console.print(f"[dim]Available: {free_gb:.1f} GB, Estimated needed: {required_gb:.1f} GB[/dim]")
            if not questionary.confirm("Continue anyway?", default=False).ask():
                return False
        return True
    except Exception:
        return True


def sanitize_path_for_filter(path):
    path_str = str(path)
    path_str = path_str.replace("\\", "/")
    path_str = path_str.replace(":", "\\:")
    path_str = path_str.replace("'", "\\'")
    return path_str


def extract_audio_for_whisper(input_file, temp_dir):
    temp_wav = os.path.join(temp_dir, "temp_audio.wav")
    try:
        console.print("[cyan]Extracting audio for analysis...[/cyan]")
        (
            ffmpeg
            .input(input_file)
            .output(temp_wav, ac=1, ar=16000, vn=None, loglevel="error")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        if not os.path.exists(temp_wav):
            console.print("[bold red]Error: Failed to extract audio file.[/bold red]")
            return None
        if os.path.getsize(temp_wav) == 0:
            console.print("[bold red]Error: Extracted audio is empty.[/bold red]")
            return None
        return temp_wav
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode() if e.stderr else "Unknown error"
        console.print(f"[bold red]Failed to extract audio: {error_msg}[/bold red]")
        return None


def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def segments_to_srt(segments):
    srt_content = []
    for i, segment in enumerate(segments, 1):
        start = format_timestamp(segment.start)
        end = format_timestamp(segment.end)
        text = segment.text.strip()
        srt_content.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(srt_content)


def segments_to_vtt(segments):
    vtt_content = ["WEBVTT\n"]
    for segment in segments:
        start = format_timestamp_vtt(segment.start)
        end = format_timestamp_vtt(segment.end)
        text = segment.text.strip()
        vtt_content.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(vtt_content)


def segments_to_txt(segments):
    return "\n".join(segment.text.strip() for segment in segments)


def segments_to_lrc(segments):
    lrc_content = []
    for segment in segments:
        minutes = int(segment.start // 60)
        seconds = segment.start % 60
        text = segment.text.strip()
        lrc_content.append(f"[{minutes:02d}:{seconds:05.2f}]{text}")
    return "\n".join(lrc_content)


def format_duration(seconds):
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def generate_subtitles(file_path):
    if not os.path.exists(file_path):
        console.print("[bold red]Error: File not found.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return

    if not os.access(file_path, os.R_OK):
        console.print("[bold red]Error: Cannot read file. Check permissions.[/bold red]")
        questionary.press_any_key_to_continue().ask()
        return

    if not has_audio_stream(file_path):
        console.print("[bold red]Error: File has no audio stream.[/bold red]")
        console.print("[dim]Subtitles require audio to transcribe.[/dim]")
        questionary.press_any_key_to_continue().ask()
        return

    has_subs, sub_count = check_existing_subtitles(file_path)
    if has_subs:
        console.print(f"[yellow]Note: This video already has {sub_count} subtitle track(s) embedded.[/yellow]")
        if not questionary.confirm("Continue generating new subtitles?", default=True).ask():
            return

    duration = get_video_duration(file_path)
    if duration > 3600:
        console.print(f"[yellow]Note: This is a long video ({format_duration(duration)}).[/yellow]")
        console.print("[dim]Transcription may take a while. Consider using a smaller model for faster results.[/dim]")
        if not questionary.confirm("Continue?", default=True).ask():
            return

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        console.print("[bold red]Error: faster-whisper is not installed.[/bold red]")
        console.print("[yellow]Install it with: pip install faster-whisper[/yellow]")
        questionary.press_any_key_to_continue().ask()
        return

    console.print("\n[bold cyan]Subtitle Generation (Whisper AI)[/bold cyan]")
    if duration > 0:
        console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

    if duration > 1800:
        default_model = "tiny.en (fastest, English only, ~75MB)"
        console.print("[dim]Tip: For long videos, smaller models are recommended.[/dim]")
    else:
        default_model = "small.en (balanced, English only, ~500MB)"

    model_choice = questionary.select(
        "Select Whisper model:",
        choices=[
            "tiny.en (fastest, English only, ~75MB)",
            "base.en (fast, English only, ~150MB)",
            "small.en (balanced, English only, ~500MB)",
            "medium.en (accurate, English only, ~1.5GB)",
            "small (balanced, multilingual, ~500MB)",
            "medium (accurate, multilingual, ~1.5GB)",
            "large-v3 (best quality, multilingual, ~3GB)",
        ],
        default=default_model
    ).ask()
    if not model_choice:
        return

    model_name = model_choice.split(" ")[0]

    language = "en"
    if not model_name.endswith(".en"):
        if questionary.confirm("Change language? (default: English)", default=False).ask():
            console.print("\n[dim]Common codes: en (English), ta (Tamil), hi (Hindi), te (Telugu),")
            console.print("ml (Malayalam), kn (Kannada), fr (French), de (German), es (Spanish), zh (Chinese)[/dim]")
            console.print("[dim]Full list: https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes[/dim]")
            language = questionary.text(
                "Enter language code (or 'auto' to detect automatically):",
                default="en"
            ).ask()
            if not language:
                return
            if language == "auto":
                language = None

    processing_mode = questionary.select(
        "Select processing mode:",
        choices=[
            "Fast (Recommended) - Optimized for speed, great accuracy",
            "Accurate - Best quality, slower processing",
        ],
        default="Fast (Recommended) - Optimized for speed, great accuracy"
    ).ask()
    if not processing_mode:
        return

    compute_type = "int8" if "Fast" in processing_mode else "float32"

    action = questionary.select(
        "What do you want to do with the subtitles?",
        choices=[
            "Export as sidecar file (.srt/.vtt)",
            "Embed into video (Soft Subtitles)",
            "Burn into video (Hard Subtitles)"
        ]
    ).ask()
    if not action:
        return

    output_format = "srt"
    if "sidecar" in action:
        output_format = questionary.select(
            "Select format:",
            choices=["srt", "vtt", "txt", "lrc"]
        ).ask()
        if not output_format:
            return

    input_p = Path(file_path)

    if "sidecar" in action:
        output_path = input_p.with_name(f"{input_p.stem}.{output_format}")
        action_result, final_output_path = check_output_file(str(output_path), "Subtitle file")
    elif "Embed" in action:
        output_path = input_p.with_name(f"{input_p.stem}_softsub{input_p.suffix}")
        action_result, final_output_path = check_output_file(str(output_path), "Video file")
    elif "Burn" in action:
        output_path = input_p.with_name(f"{input_p.stem}_hardsub{input_p.suffix}")
        action_result, final_output_path = check_output_file(str(output_path), "Video file")
        if action_result != 'cancel' and not check_disk_space(file_path, multiplier=2):
            return
    else:
        action_result = 'proceed'
        final_output_path = None

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        questionary.press_any_key_to_continue().ask()
        return

    crf = "23"
    if "Burn" in action:
        quality = questionary.select(
            "Select Video Quality (CRF):",
            choices=["High (18)", "Medium (23)", "Low (28)"],
            default="Medium (23)"
        ).ask()
        if not quality:
            return
        crf = quality.split("(")[1].strip(")")

    with tempfile.TemporaryDirectory() as temp_dir:
        wav_path = extract_audio_for_whisper(file_path, temp_dir)
        if not wav_path:
            questionary.press_any_key_to_continue().ask()
            return

        console.print(f"[cyan]Loading Whisper model '{model_name}'...[/cyan]")
        console.print("[dim]First run will download the model (may take a few minutes)[/dim]")

        try:
            model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
        except Exception as e:
            error_msg = str(e)
            if "out of memory" in error_msg.lower():
                console.print("[bold red]Error: Not enough memory to load model.[/bold red]")
                console.print("[yellow]Try using a smaller model (tiny or base).[/yellow]")
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                console.print("[bold red]Error: Failed to download model. Check your internet connection.[/bold red]")
            else:
                console.print(f"[bold red]Failed to load model: {e}[/bold red]")
            questionary.press_any_key_to_continue().ask()
            return

        console.print("[cyan]Transcribing audio...[/cyan]")

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Transcribing...", total=None)
                segments_generator, info = model.transcribe(
                    wav_path,
                    language=language,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
                segments = list(segments_generator)
                progress.update(task, completed=100)

        except KeyboardInterrupt:
            console.print("\n[yellow]Transcription cancelled by user.[/yellow]")
            questionary.press_any_key_to_continue().ask()
            return
        except Exception as e:
            error_msg = str(e)
            if "out of memory" in error_msg.lower():
                console.print("[bold red]Error: Ran out of memory during transcription.[/bold red]")
                console.print("[yellow]Try using a smaller model or processing a shorter video.[/yellow]")
            else:
                console.print(f"[bold red]Transcription failed: {e}[/bold red]")
            questionary.press_any_key_to_continue().ask()
            return

        if not segments:
            console.print("[bold yellow]No speech detected in audio.[/bold yellow]")
            console.print("[dim]The video might be silent, have only music, or the audio quality is too low.[/dim]")
            questionary.press_any_key_to_continue().ask()
            return

        detected_lang = info.language if language is None else language
        console.print(f"[green]Detected language: {detected_lang}[/green]")
        console.print(f"[green]Transcribed {len(segments)} segments[/green]")

        if output_format == "srt" or "Embed" in action or "Burn" in action:
            subtitle_content = segments_to_srt(segments)
            sub_ext = "srt"
        elif output_format == "vtt":
            subtitle_content = segments_to_vtt(segments)
            sub_ext = "vtt"
        elif output_format == "txt":
            subtitle_content = segments_to_txt(segments)
            sub_ext = "txt"
        elif output_format == "lrc":
            subtitle_content = segments_to_lrc(segments)
            sub_ext = "lrc"
        else:
            subtitle_content = segments_to_srt(segments)
            sub_ext = "srt"

        if not subtitle_content.strip():
            console.print("[bold yellow]Warning: Generated subtitles are empty.[/bold yellow]")
            questionary.press_any_key_to_continue().ask()
            return

        sub_temp_path = os.path.join(temp_dir, f"output.{sub_ext}")
        try:
            with open(sub_temp_path, "w", encoding="utf-8") as f:
                f.write(subtitle_content)
        except IOError as e:
            console.print(f"[bold red]Error writing subtitle file: {e}[/bold red]")
            questionary.press_any_key_to_continue().ask()
            return

        try:
            if "sidecar" in action:
                with open(final_output_path, "w", encoding="utf-8") as f:
                    f.write(subtitle_content)
                console.print(f"[bold green]Saved subtitles to: {final_output_path}[/bold green]")

            elif "Embed" in action:
                console.print("[cyan]Embedding subtitles (Soft Subs)...[/cyan]")
                ext = input_p.suffix.lower()
                scodec = "mov_text" if ext in ['.mp4', '.m4v', '.mov'] else "srt"
                stream = ffmpeg.input(file_path)
                sub_stream = ffmpeg.input(sub_temp_path)
                out = ffmpeg.output(
                    stream, sub_stream, str(final_output_path),
                    c='copy', **{'c:s': scodec}, **{'metadata:s:s:0': f'language={detected_lang}'}
                )
                if action_result == 'overwrite':
                    out = out.overwrite_output()
                if run_command(out, "Embedding subtitles...", show_progress=True):
                    console.print(f"[bold green]Created: {final_output_path}[/bold green]")
                else:
                    console.print("[bold red]Failed to embed subtitles.[/bold red]")

            elif "Burn" in action:
                console.print("[cyan]Burning subtitles (Hard Subs)...[/cyan]")
                console.print("[dim]This requires re-encoding and may take a while...[/dim]")
                stream = ffmpeg.input(file_path)
                video = stream.video.filter('subtitles', sub_temp_path)
                audio = stream.audio
                out = ffmpeg.output(
                    video, audio, str(final_output_path),
                    vcodec='libx264', acodec='copy', crf=crf, preset='fast'
                )
                if action_result == 'overwrite':
                    out = out.overwrite_output()
                if run_command(out, "Burning subtitles (Re-encoding)...", show_progress=True):
                    console.print(f"[bold green]Created: {final_output_path}[/bold green]")
                else:
                    console.print("[bold red]Failed to burn subtitles.[/bold red]")

        except PermissionError:
            console.print("[bold red]Error: Permission denied. Cannot write to output location.[/bold red]")
            console.print("[dim]Try saving to a different location or check folder permissions.[/dim]")
        except IOError as e:
            console.print(f"[bold red]Error writing output: {e}[/bold red]")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}[/bold red]")

    questionary.press_any_key_to_continue().ask()
