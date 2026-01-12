import os
import sys
import logging
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import questionary
from rich.console import Console

from peg_this.features.audio import extract_audio, remove_audio
from peg_this.features.batch import batch_convert
from peg_this.features.compress import compress_video, change_resolution
from peg_this.features.convert import convert_file, convert_image, resize_image, rotate_image, flip_image
from peg_this.features.crop import crop_video, crop_image
from peg_this.features.effects import add_watermark, merge_audio_video
from peg_this.features.frames import extract_frames, split_video
from peg_this.features.inspect import inspect_file
from peg_this.features.join import join_videos
from peg_this.features.speed import change_speed, reverse_video
from peg_this.features.subtitle import generate_subtitles
from peg_this.features.trim import trim_video
from peg_this.utils.ffmpeg_utils import check_ffmpeg_ffprobe
from peg_this.utils.ui_utils import select_media_file

log_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ffmpeg_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w')
    ]
)

console = Console()
VERSION = "4.2.0"

LOGO = """[bold magenta]
╔════════════════════════════════════════════════════════════════════════╗
║                                                                        ║
║   ██████╗ ███████╗ ██████╗       ████████╗██╗  ██╗██╗███████╗          ║
║   ██╔══██╗██╔════╝██╔════╝       ╚══██╔══╝██║  ██║██║██╔════╝          ║
║   ██████╔╝█████╗  ██║  ███╗█████╗   ██║   ███████║██║███████╗          ║
║   ██╔═══╝ ██╔══╝  ██║   ██║╚════╝   ██║   ██╔══██║██║╚════██║          ║
║   ██║     ███████╗╚██████╔╝         ██║   ██║  ██║██║███████║          ║
║   ╚═╝     ╚══════╝ ╚═════╝          ╚═╝   ╚═╝  ╚═╝╚═╝╚══════╝          ║
║                                                                        ║
║                        [cyan]~ peg_this v{version} ~[/cyan]                             ║
║                  [dim]Your friendly CLI media toolkit[/dim]                       ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
[/bold magenta]"""


def show_landing():
    console.clear()
    console.print(LOGO.format(version=VERSION), justify="center")
    console.print("[dim]Peg it. Convert it. Done.[/dim]", justify="center")
    console.print()


def video_edit_menu():
    action = questionary.select(
        "Select an edit action:",
        choices=[
            "Trim Video",
            "Crop Video (Visual)",
            "Split Video",
            "Join Multiple Videos",
            questionary.Separator(),
            "← Back"
        ]
    ).ask()

    if action == "← Back" or action is None:
        return

    if action == "Join Multiple Videos":
        join_videos()
        return

    file_path = select_media_file(filter_type="video")
    if not file_path:
        return

    actions = {
        "Trim Video": trim_video,
        "Crop Video (Visual)": crop_video,
        "Split Video": split_video,
    }

    if action in actions:
        actions[action](file_path)


def video_audio_menu():
    action = questionary.select(
        "Select an audio action:",
        choices=[
            "Extract Audio",
            "Remove Audio",
            "Merge Audio with Video",
            questionary.Separator(),
            "← Back"
        ]
    ).ask()

    if action == "← Back" or action is None:
        return

    file_path = select_media_file(filter_type="video")
    if not file_path:
        return

    actions = {
        "Extract Audio": extract_audio,
        "Remove Audio": remove_audio,
        "Merge Audio with Video": merge_audio_video,
    }

    if action in actions:
        actions[action](file_path)


def subtitle_menu():
    file_path = select_media_file(filter_type="video")
    if not file_path:
        return
    generate_subtitles(file_path)


def video_convert_menu():
    action = questionary.select(
        "Select a convert action:",
        choices=[
            "Convert Format",
            "Compress Video",
            "Change Resolution",
            questionary.Separator(),
            "← Back"
        ]
    ).ask()

    if action == "← Back" or action is None:
        return

    file_path = select_media_file(filter_type="video")
    if not file_path:
        return

    actions = {
        "Convert Format": convert_file,
        "Compress Video": compress_video,
        "Change Resolution": change_resolution,
    }

    if action in actions:
        actions[action](file_path)


def video_effects_menu():
    action = questionary.select(
        "Select an effect:",
        choices=[
            "Change Speed",
            "Reverse Video",
            "Add Watermark",
            "Extract Frames",
            questionary.Separator(),
            "← Back"
        ]
    ).ask()

    if action == "← Back" or action is None:
        return

    file_path = select_media_file(filter_type="video")
    if not file_path:
        return

    actions = {
        "Change Speed": change_speed,
        "Reverse Video": reverse_video,
        "Add Watermark": add_watermark,
        "Extract Frames": extract_frames,
    }

    if action in actions:
        actions[action](file_path)


def image_menu():
    action = questionary.select(
        "Select an image action:",
        choices=[
            "Convert Format",
            "Resize",
            "Rotate",
            "Flip",
            "Crop (Visual)",
            questionary.Separator(),
            "← Back"
        ]
    ).ask()

    if action == "← Back" or action is None:
        return

    file_path = select_media_file(filter_type="image")
    if not file_path:
        return

    actions = {
        "Convert Format": convert_image,
        "Resize": resize_image,
        "Rotate": rotate_image,
        "Flip": flip_image,
        "Crop (Visual)": crop_image,
    }

    if action in actions:
        actions[action](file_path)


def inspect_menu():
    file_path = select_media_file()
    if file_path:
        inspect_file(file_path)


def main_menu():
    check_ffmpeg_ffprobe()
    show_landing()

    while True:
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Separator("─────── Video ───────"),
                "✂️  Edit (Trim, Crop, Split, Join)",
                "🎵  Audio (Extract, Remove, Merge)",
                "💬  Subtitles (AI Generate)",
                "🔄  Convert (Format, Compress, Resize)",
                "✨  Effects (Speed, Reverse, Watermark)",
                questionary.Separator("─────── Image ───────"),
                "🖼️  Image Tools",
                questionary.Separator("─────── Other ───────"),
                "📦  Batch Convert",
                "🔍  Inspect File",
                questionary.Separator(),
                "👋  Exit"
            ],
            use_indicator=True
        ).ask()

        if choice is None or "Exit" in choice:
            console.print()
            console.print("[bold magenta]Thanks for using peg_this![/bold magenta]")
            console.print("[dim]Peg it. Convert it. Done.[/dim]")
            console.print()
            console.print("[dim italic]Built with ❤️ by Hariharen[/dim italic]")
            break
        elif "Edit" in choice:
            video_edit_menu()
        elif "Audio" in choice:
            video_audio_menu()
        elif "Subtitles" in choice:
            subtitle_menu()
        elif "Convert" in choice:
            video_convert_menu()
        elif "Effects" in choice:
            video_effects_menu()
        elif "Image" in choice:
            image_menu()
        elif "Batch" in choice:
            batch_convert()
        elif "Inspect" in choice:
            inspect_menu()


def main():
    try:
        main_menu()
    except (KeyboardInterrupt, EOFError):
        logging.info("Operation cancelled by user.")
        console.print("\n[bold]Operation cancelled. Goodbye![/bold]")
    except Exception as e:
        logging.exception("An unexpected error occurred.")
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        console.print(f"Details have been logged to {log_file}")


if __name__ == "__main__":
    main()
