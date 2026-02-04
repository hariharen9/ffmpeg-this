from pathlib import Path

import ffmpeg
import questionary
from rich.console import Console

from peg_this.utils.ffmpeg_utils import run_command, has_audio_stream
from peg_this.utils.validation import (
    validate_input_file, check_output_file, check_has_video_stream, press_continue,
    get_video_duration, format_duration, validate_time_input
)

console = Console()


def extract_audio(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    if not has_audio_stream(file_path):
        console.print("[bold red]Error: No audio stream found in the file.[/bold red]")
        press_continue()
        return

    audio_format = questionary.select(
        "Select audio format:",
        choices=["mp3", "flac", "wav"]
    ).ask()
    if not audio_format:
        return

    output_file = f"{Path(file_path).stem}_audio.{audio_format}"
    action_result, final_output = check_output_file(output_file, "Audio file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path).output(
        final_output,
        vn=None,
        acodec='libmp3lame' if audio_format == 'mp3' else audio_format
    )

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Extracting audio to {audio_format.upper()}...", show_progress=True):
        console.print(f"[bold green]Successfully extracted audio to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to extract audio.[/bold red]")

    press_continue()


def remove_audio(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    if not check_has_video_stream(file_path):
        console.print("[bold red]Error: No video stream found in the file.[/bold red]")
        press_continue()
        return

    output_file = f"{Path(file_path).stem}_no_audio{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Video file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    stream = ffmpeg.input(file_path).output(final_output, vcodec='copy', an=None)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Removing audio track...", show_progress=True):
        console.print(f"[bold green]Successfully removed audio, saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to remove audio.[/bold red]")

    press_continue()


def adjust_volume(file_path):
    """Adjust the volume of a video or audio file."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not has_audio_stream(file_path):
        console.print("[bold red]Error: No audio stream found in the file.[/bold red]")
        press_continue()
        return

    is_video = check_has_video_stream(file_path)

    console.print("[dim]Current file has audio that can be adjusted.[/dim]")

    method = questionary.select(
        "How would you like to adjust volume?",
        choices=[
            "Use preset (50%, 150%, 200%, etc.)",
            "Enter custom multiplier (e.g., 1.5 for 150%)",
            "Enter dB value (e.g., +6dB or -3dB)",
            "← Back"
        ]
    ).ask()

    if method == "← Back" or method is None:
        return

    volume_filter = None

    if "preset" in method:
        preset = questionary.select(
            "Select volume level:",
            choices=[
                "25% (Quieter)",
                "50% (Half volume)",
                "75% (Slightly quieter)",
                "125% (Slightly louder)",
                "150% (1.5x louder)",
                "200% (2x louder)",
                "300% (3x louder)"
            ]
        ).ask()

        if preset is None:
            return

        # Extract percentage from choice
        percent = int(preset.split("%")[0])
        volume_filter = str(percent / 100)

    elif "multiplier" in method:
        multiplier = questionary.text(
            "Enter volume multiplier (0.5 = 50%, 1.5 = 150%, 2.0 = 200%):",
            default="1.5"
        ).ask()

        if multiplier is None:
            return

        try:
            vol = float(multiplier)
            if vol <= 0:
                console.print("[bold red]Volume multiplier must be greater than 0.[/bold red]")
                press_continue()
                return
            volume_filter = str(vol)
        except ValueError:
            console.print("[bold red]Invalid multiplier value.[/bold red]")
            press_continue()
            return

    else:  # dB value
        db_value = questionary.text(
            "Enter dB adjustment (e.g., +6dB, -3dB, 10dB):",
            default="+6dB"
        ).ask()

        if db_value is None:
            return

        # Clean up the input
        db_clean = db_value.strip().upper().replace("DB", "dB")
        if not db_clean.endswith("dB"):
            db_clean += "dB"

        volume_filter = db_clean

    suffix = "volume_adjusted"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)

    if is_video:
        # Video file: copy video, adjust audio
        audio = input_stream.audio.filter('volume', volume_filter)
        stream = ffmpeg.output(input_stream.video, audio, final_output, **{'c:v': 'copy'})
    else:
        # Audio only file
        audio = input_stream.filter('volume', volume_filter)
        stream = ffmpeg.output(audio, final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Adjusting volume to {volume_filter}...", show_progress=True):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to adjust volume.[/bold red]")

    press_continue()


def audio_fade(file_path):
    """Apply fade in/out effects to audio."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not has_audio_stream(file_path):
        console.print("[bold red]Error: No audio stream found in the file.[/bold red]")
        press_continue()
        return

    is_video = check_has_video_stream(file_path)
    duration = get_video_duration(file_path)

    if duration <= 0:
        console.print("[bold red]Error: Could not determine file duration.[/bold red]")
        press_continue()
        return

    console.print(f"[dim]File duration: {format_duration(duration)}[/dim]")

    fade_type = questionary.select(
        "What type of audio fade?",
        choices=[
            "Fade In (start)",
            "Fade Out (end)",
            "Both (fade in and out)",
            "← Back"
        ]
    ).ask()

    if fade_type == "← Back" or fade_type is None:
        return

    # Fade curve types
    curve_type = questionary.select(
        "Select fade curve:",
        choices=[
            "tri - Linear (default)",
            "qsin - Quarter sine",
            "hsin - Half sine",
            "log - Logarithmic",
            "exp - Exponential",
            "par - Parabola"
        ]
    ).ask()

    if curve_type is None:
        return

    curve = curve_type.split(" - ")[0]

    fade_in_secs = 0
    fade_out_secs = 0

    if "In" in fade_type or "Both" in fade_type:
        fade_in_dur = questionary.text(
            "Fade in duration (seconds):",
            default="2"
        ).ask()

        if fade_in_dur is None:
            return

        fade_in_secs = validate_time_input(fade_in_dur, duration, "Fade in duration")
        if fade_in_secs is None:
            press_continue()
            return

    if "Out" in fade_type or "Both" in fade_type:
        fade_out_dur = questionary.text(
            "Fade out duration (seconds):",
            default="2"
        ).ask()

        if fade_out_dur is None:
            return

        fade_out_secs = validate_time_input(fade_out_dur, duration, "Fade out duration")
        if fade_out_secs is None:
            press_continue()
            return

    suffix = "audio_fade"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)
    audio = input_stream.audio

    # Apply fade in
    if fade_in_secs > 0:
        audio = audio.filter('afade', t='in', st=0, d=fade_in_secs, curve=curve)

    # Apply fade out
    if fade_out_secs > 0:
        start_time = duration - fade_out_secs
        audio = audio.filter('afade', t='out', st=start_time, d=fade_out_secs, curve=curve)

    if is_video:
        stream = ffmpeg.output(input_stream.video, audio, final_output, **{'c:v': 'copy'})
    else:
        stream = ffmpeg.output(audio, final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, "Applying audio fade...", show_progress=True):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to apply audio fade.[/bold red]")

    press_continue()


def normalize_audio(file_path):
    """Normalize audio levels using various methods."""
    if not validate_input_file(file_path):
        press_continue()
        return

    if not has_audio_stream(file_path):
        console.print("[bold red]Error: No audio stream found in the file.[/bold red]")
        press_continue()
        return

    is_video = check_has_video_stream(file_path)

    console.print("[dim]Audio normalization adjusts volume levels for consistent loudness.[/dim]")

    method = questionary.select(
        "Select normalization method:",
        choices=[
            "EBU R128 (Broadcast standard, recommended)",
            "Peak Normalization (Maximize without clipping)",
            "RMS Normalization (Average loudness)",
            "Dynamic Normalization (Compress dynamic range)",
            "← Back"
        ]
    ).ask()

    if method == "← Back" or method is None:
        return

    audio_filter = None
    filter_desc = ""

    if "EBU R128" in method:
        target_lufs = questionary.select(
            "Target loudness (LUFS):",
            choices=[
                "-14 LUFS (Streaming: Spotify, YouTube)",
                "-16 LUFS (Broadcast standard)",
                "-18 LUFS (Quieter, more dynamic range)",
                "-23 LUFS (EBU R128 reference)",
                "Custom"
            ]
        ).ask()

        if target_lufs is None:
            return

        if "Custom" in target_lufs:
            custom_lufs = questionary.text(
                "Enter target LUFS (e.g., -14):",
                default="-14"
            ).ask()
            if custom_lufs is None:
                return
            try:
                lufs_val = float(custom_lufs)
            except ValueError:
                console.print("[bold red]Invalid LUFS value.[/bold red]")
                press_continue()
                return
        else:
            lufs_val = float(target_lufs.split(" ")[0])

        audio_filter = ("loudnorm", {"I": str(lufs_val), "TP": "-1.5", "LRA": "11"})
        filter_desc = f"EBU R128 to {lufs_val} LUFS"

    elif "Peak" in method:
        target_db = questionary.select(
            "Target peak level:",
            choices=[
                "0 dB (Maximum, no headroom)",
                "-1 dB (Recommended)",
                "-3 dB (Safe headroom)",
                "-6 dB (Conservative)"
            ]
        ).ask()

        if target_db is None:
            return

        db_val = float(target_db.split(" ")[0])
        audio_filter = ("loudnorm", {"I": "-24", "TP": str(db_val), "LRA": "7", "linear": "true"})
        filter_desc = f"Peak normalize to {db_val} dB"

    elif "RMS" in method:
        target_rms = questionary.select(
            "Target RMS level:",
            choices=[
                "-14 dB (Loud)",
                "-18 dB (Standard)",
                "-20 dB (Moderate)",
                "-24 dB (Quiet)"
            ]
        ).ask()

        if target_rms is None:
            return

        rms_val = float(target_rms.split(" ")[0])
        audio_filter = ("loudnorm", {"I": str(rms_val), "TP": "-1", "LRA": "11"})
        filter_desc = f"RMS normalize to {rms_val} dB"

    else:  # Dynamic normalization
        strength = questionary.select(
            "Compression strength:",
            choices=[
                "Light (Preserve dynamics)",
                "Medium (Balanced)",
                "Heavy (Very consistent loudness)"
            ]
        ).ask()

        if strength is None:
            return

        if "Light" in strength:
            audio_filter = ("dynaudnorm", {"f": "150", "g": "15", "p": "0.7", "m": "10"})
        elif "Medium" in strength:
            audio_filter = ("dynaudnorm", {"f": "250", "g": "25", "p": "0.8", "m": "15"})
        else:
            audio_filter = ("dynaudnorm", {"f": "500", "g": "31", "p": "0.95", "m": "20"})

        filter_desc = f"{strength.split(' ')[0]} dynamic normalization"

    suffix = "normalized"
    output_file = f"{Path(file_path).stem}_{suffix}{Path(file_path).suffix}"
    action_result, final_output = check_output_file(output_file, "Output file")

    if action_result == 'cancel':
        console.print("[yellow]Operation cancelled.[/yellow]")
        press_continue()
        return

    input_stream = ffmpeg.input(file_path)

    # Apply filter
    filter_name, filter_args = audio_filter
    audio = input_stream.audio.filter(filter_name, **filter_args)

    if is_video:
        stream = ffmpeg.output(input_stream.video, audio, final_output, **{'c:v': 'copy'})
    else:
        stream = ffmpeg.output(audio, final_output)

    if action_result == 'overwrite':
        stream = stream.overwrite_output()

    if run_command(stream, f"Applying {filter_desc}...", show_progress=True):
        console.print(f"[bold green]Successfully saved to {final_output}[/bold green]")
    else:
        console.print("[bold red]Failed to normalize audio.[/bold red]")

    press_continue()
