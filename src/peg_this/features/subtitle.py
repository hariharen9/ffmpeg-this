import os
import tempfile
from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from peg_this.utils.ffmpeg_utils import run_command, run_command_list, has_audio_stream, get_global_encoding_args
from peg_this.settings import Settings
from peg_this.utils.validation import (
    validate_input_file, check_output_file, check_disk_space,
    get_video_duration, format_duration, press_continue
)

console = Console()


def check_existing_subtitles(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        subtitle_streams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'subtitle']
        return len(subtitle_streams) > 0, len(subtitle_streams)
    except Exception:
        return False, 0


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


def generate_subtitles(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    if not has_audio_stream(file_path):
        console.print("[bold red]Error: File has no audio stream.[/bold red]")
        console.print("[dim]Subtitles require audio to transcribe.[/dim]")
        press_continue()
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
        press_continue()
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
        press_continue()
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
            press_continue()
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
            press_continue()
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
            press_continue()
            return
        except Exception as e:
            error_msg = str(e)
            if "out of memory" in error_msg.lower():
                console.print("[bold red]Error: Ran out of memory during transcription.[/bold red]")
                console.print("[yellow]Try using a smaller model or processing a shorter video.[/yellow]")
            else:
                console.print(f"[bold red]Transcription failed: {e}[/bold red]")
            press_continue()
            return

        if not segments:
            console.print("[bold yellow]No speech detected in audio.[/bold yellow]")
            console.print("[dim]The video might be silent, have only music, or the audio quality is too low.[/dim]")
            press_continue()
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
            press_continue()
            return

        sub_temp_path = os.path.join(temp_dir, f"output.{sub_ext}")
        try:
            with open(sub_temp_path, "w", encoding="utf-8") as f:
                f.write(subtitle_content)
        except IOError as e:
            console.print(f"[bold red]Error writing subtitle file: {e}[/bold red]")
            press_continue()
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
                burn_encoding_args = get_global_encoding_args(quality="medium", crf=int(crf))
                burn_encoding_args['acodec'] = 'copy'
                out = ffmpeg.output(
                    video, audio, str(final_output_path),
                    **burn_encoding_args
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

    press_continue()


def brainrot_captions(file_path):
    """Generate TikTok/Reels style animated captions with word-by-word timing."""
    import subprocess

    if not validate_input_file(file_path):
        press_continue()
        return

    if not has_audio_stream(file_path):
        console.print("[bold red]Error: File has no audio stream.[/bold red]")
        console.print("[dim]Captions require audio to transcribe.[/dim]")
        press_continue()
        return

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        console.print("[bold red]Error: faster-whisper is not installed.[/bold red]")
        console.print("[yellow]Install it with: pip install faster-whisper[/yellow]")
        press_continue()
        return

    # Check video resolution for font sizing
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        video_height = int(video_stream['height'])
        video_width = int(video_stream['width'])
    except Exception:
        video_height = 1080
        video_width = 1920

    duration = get_video_duration(file_path)
    console.print(f"\n[bold cyan]Brainrot Captions Generator[/bold cyan]")
    if duration > 0:
        console.print(f"[dim]Video duration: {format_duration(duration)}[/dim]")

    # Style selection
    style = questionary.select(
        "Select caption style:",
        choices=[
            "Classic (White + Black outline)",
            "Highlighted (Current word in yellow)",
            "Colorful (Rainbow gradient)",
            "Neon Glow (Cyan with glow effect)",
            "Bold Impact (All caps, heavy)",
            "← Back"
        ]
    ).ask()

    if style == "← Back" or style is None:
        return

    # Position selection
    position = questionary.select(
        "Caption position:",
        choices=[
            "Center (Default)",
            "Bottom Third",
            "Top Third",
        ]
    ).ask()

    if not position:
        return

    # Model selection - smaller models for speed since we need word-level
    model_choice = questionary.select(
        "Select Whisper model:",
        choices=[
            "tiny.en (fastest, ~75MB)",
            "base.en (fast, ~150MB)",
            "small.en (balanced, ~500MB)",
            "small (multilingual, ~500MB)",
        ],
        default="base.en (fast, ~150MB)"
    ).ask()

    if not model_choice:
        return

    model_name = model_choice.split(" ")[0]

    # Output file
    input_p = Path(file_path)
    output_path = input_p.with_name(f"{input_p.stem}_brainrot{input_p.suffix}")
    action_result, final_output = check_output_file(str(output_path), "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    if not check_disk_space(file_path, multiplier=2):
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract audio
        wav_path = extract_audio_for_whisper(file_path, temp_dir)
        if not wav_path:
            press_continue()
            return

        console.print(f"[cyan]Loading Whisper model '{model_name}'...[/cyan]")

        try:
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
        except Exception as e:
            console.print(f"[bold red]Failed to load model: {e}[/bold red]")
            press_continue()
            return

        console.print("[cyan]Transcribing with word-level timestamps...[/cyan]")

        try:
            segments_generator, info = model.transcribe(
                wav_path,
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
            )
            segments = list(segments_generator)
        except Exception as e:
            console.print(f"[bold red]Transcription failed: {e}[/bold red]")
            press_continue()
            return

        if not segments:
            console.print("[bold yellow]No speech detected in audio.[/bold yellow]")
            press_continue()
            return

        # Collect all words with timestamps
        all_words = []
        for segment in segments:
            if segment.words:
                for word in segment.words:
                    all_words.append({
                        'text': word.word.strip(),
                        'start': word.start,
                        'end': word.end
                    })

        if not all_words:
            console.print("[bold yellow]No word-level timestamps available.[/bold yellow]")
            console.print("[dim]Try using a different model.[/dim]")
            press_continue()
            return

        console.print(f"[green]Found {len(all_words)} words[/green]")

        # Generate ASS subtitle file
        ass_fd, ass_path = tempfile.mkstemp(suffix=".ass")
        os.close(ass_fd)

        # Calculate font size based on video height
        base_font_size = int(video_height / 12)  # Roughly 90px for 1080p

        # Font fallback logic
        # On Linux, Impact is rarely installed. Arial is more common.
        # But for ASS, we can only specify one font per style.
        # We'll use Impact but provide a way to change it if needed, or just hope libass falls back.
        # A better way is to use a more generic font name that fontconfig maps to something bold.
        primary_font = "Impact"
        fallback_font = "Arial Black" if os.name != 'nt' else "Impact"

        # Position calculation
        if "Center" in position:
            margin_v = int(video_height * 0.4)  # 40% from bottom = center-ish
        elif "Bottom" in position:
            margin_v = int(video_height * 0.15)  # 15% from bottom
        else:  # Top
            margin_v = int(video_height * 0.75)  # 75% from bottom = top area

        # Style-specific settings
        style_configs = {
            "Classic": {
                "primary_color": "&H00FFFFFF",  # White
                "outline_color": "&H00000000",  # Black
                "outline_width": 4,
                "shadow": 2,
                "bold": -1,
                "highlight_color": None
            },
            "Highlighted": {
                "primary_color": "&H00FFFFFF",  # White
                "outline_color": "&H00000000",  # Black
                "outline_width": 3,
                "shadow": 1,
                "bold": -1,
                "highlight_color": "&H0000FFFF"  # Yellow (BGR format)
            },
            "Colorful": {
                "primary_color": "&H00FF00FF",  # Magenta
                "outline_color": "&H00000000",  # Black
                "outline_width": 3,
                "shadow": 2,
                "bold": -1,
                "highlight_color": None,
                "rainbow": True
            },
            "Neon": {
                "primary_color": "&H00FFFF00",  # Cyan
                "outline_color": "&H00FF00FF",  # Magenta
                "outline_width": 2,
                "shadow": 4,
                "bold": -1,
                "highlight_color": None
            },
            "Bold": {
                "primary_color": "&H00FFFFFF",  # White
                "outline_color": "&H00000000",  # Black
                "outline_width": 5,
                "shadow": 3,
                "bold": -1,
                "highlight_color": None,
                "uppercase": True
            }
        }

        # Get style config
        style_key = style.split(" ")[0]
        config = style_configs.get(style_key, style_configs["Classic"])

        # Rainbow colors for Colorful style
        rainbow_colors = [
            "&H000000FF",  # Red
            "&H000080FF",  # Orange
            "&H0000FFFF",  # Yellow
            "&H0000FF00",  # Green
            "&H00FFFF00",  # Cyan
            "&H00FF0000",  # Blue
            "&H00FF00FF",  # Magenta
        ]

        # Generate ASS content
        ass_content = f"""[Script Info]
Title: Brainrot Captions
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fallback_font},{base_font_size},{config['primary_color']},&H000000FF,{config['outline_color']},&H00000000,{config['bold']},0,0,0,100,100,0,0,1,{config['outline_width']},{config['shadow']},2,10,10,{margin_v},1
Style: Highlight,{fallback_font},{base_font_size},{config.get('highlight_color', '&H0000FFFF')},&H000000FF,{config['outline_color']},&H00000000,{config['bold']},0,0,0,100,100,0,0,1,{config['outline_width']},{config['shadow']},2,10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        def format_ass_time(seconds):
            """Format time for ASS format (H:MM:SS.cc)"""
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            cs = int((seconds % 1) * 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        # Group words into phrases (3-5 words each for readability)
        phrases = []
        current_phrase = []
        words_per_phrase = 4

        for i, word in enumerate(all_words):
            current_phrase.append(word)
            if len(current_phrase) >= words_per_phrase or i == len(all_words) - 1:
                if current_phrase:
                    phrases.append(current_phrase)
                    current_phrase = []

        # Generate events - show phrase with highlighted current word
        for phrase in phrases:
            phrase_start = phrase[0]['start']
            phrase_end = phrase[-1]['end']

            # For each word in the phrase, create an event highlighting that word
            for word_idx, word in enumerate(phrase):
                word_start = word['start']
                word_end = word['end']

                # Build the text with current word highlighted
                text_parts = []
                for j, w in enumerate(phrase):
                    word_text = w['text']

                    # Apply uppercase if Bold style
                    if config.get('uppercase'):
                        word_text = word_text.upper()

                    if j == word_idx:
                        # Current word - apply highlight or scale effect
                        if config.get('highlight_color'):
                            text_parts.append(f"{{\\c{config['highlight_color']}\\fscx110\\fscy110}}{word_text}{{\\c{config['primary_color']}\\fscx100\\fscy100}}")
                        elif config.get('rainbow'):
                            color = rainbow_colors[j % len(rainbow_colors)]
                            text_parts.append(f"{{\\c{color}\\fscx115\\fscy115}}{word_text}{{\\fscx100\\fscy100}}")
                        else:
                            text_parts.append(f"{{\\fscx110\\fscy110}}{word_text}{{\\fscx100\\fscy100}}")
                    else:
                        if config.get('rainbow'):
                            color = rainbow_colors[j % len(rainbow_colors)]
                            text_parts.append(f"{{\\c{color}}}{word_text}")
                        else:
                            text_parts.append(word_text)

                full_text = " ".join(text_parts)

                # Add subtle animation
                full_text = f"{{\\fad(50,50)}}{full_text}"

                start_time = format_ass_time(word_start)
                end_time = format_ass_time(word_end)

                ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{full_text}\n"

        # Write ASS file
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        console.print("[cyan]Burning captions into video...[/cyan]")
        console.print("[dim]This requires re-encoding and may take a while...[/dim]")

        # Escape path for ASS filter
        ass_path_escaped = ass_path.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")

        # Build FFmpeg command
        cmd = ['ffmpeg']
        if action_result == 'overwrite':
            cmd.append('-y')

        brainrot_encoding_args = Settings().get_encoder_list_args(quality="high", crf=18)

        cmd.extend([
            '-i', file_path,
            '-vf', f"ass='{ass_path_escaped}'"
        ])
        cmd.extend(brainrot_encoding_args)
        cmd.extend([
            '-c:a', 'copy',
            '-pix_fmt', 'yuv420p',
            final_output
        ])

        if run_command_list(cmd, "Burning captions into video...", show_progress=True, input_file=file_path):
            console.print(f"[bold green]Successfully created {final_output}[/bold green]")
        else:
            console.print("[bold red]Failed to burn captions.[/bold red]")

    press_continue()
