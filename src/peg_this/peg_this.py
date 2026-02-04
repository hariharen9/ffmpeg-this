import os
import sys
import logging
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import questionary
from prompt_toolkit.keys import Keys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.align import Align

from peg_this.features.audio import extract_audio, remove_audio, adjust_volume, audio_fade, normalize_audio
from peg_this.features.batch import batch_convert
from peg_this.features.compress import compress_video, change_resolution
from peg_this.features.convert import convert_file, convert_image, resize_image, rotate_image, flip_image
from peg_this.features.crop import crop_video, crop_image
from peg_this.features.effects import add_watermark, merge_audio_video, video_fade, loop_video, color_correction, denoise_video, picture_in_picture, blur_region, auto_blur_faces, audio_visualizer, rotate_video, flip_video, remove_background
from peg_this.features.frames import extract_frames, split_video
from peg_this.features.inspect import inspect_file
from peg_this.features.join import join_videos
from peg_this.features.speed import change_speed, reverse_video
from peg_this.features.subtitle import generate_subtitles, brainrot_captions
from peg_this.features.trim import trim_video
from peg_this.features.advanced import create_slideshow, metadata_editor, stabilize_video, create_gif_advanced
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
   ██████╗ ███████╗ ██████╗       ████████╗██╗  ██╗██╗███████╗
   ██╔══██╗██╔════╝██╔════╝       ╚══██╔══╝██║  ██║██║██╔════╝
   ██████╔╝█████╗  ██║  ███╗█████╗   ██║   ███████║██║███████╗
   ██╔═══╝ ██╔══╝  ██║   ██║╚════╝   ██║   ██╔══██║██║╚════██║
   ██║     ███████╗╚██████╔╝         ██║   ██║  ██║██║███████║
   ╚═╝     ╚══════╝ ╚═════╝          ╚═╝   ╚═╝  ╚═╝╚═╝╚══════╝
[/bold magenta]"""


def create_feature_panel(title, items, color="cyan"):
    """Create a panel with feature list."""
    content = "\n".join([f"[dim]•[/dim] {item}" for item in items])
    return Panel(
        content,
        title=f"[bold {color}]{title}[/bold {color}]",
        border_style=f"dim {color}",
        padding=(0, 1),
        width=28
    )


def show_landing():
    console.clear()

    # Logo and version
    console.print(Align.center(LOGO))
    console.print(Align.center(f"[cyan]v{VERSION}[/cyan]"))
    console.print(Align.center("[dim italic]Studio in a Shell[/dim italic]"))
    console.print()

    # Feature panels
    panels = [
        create_feature_panel("🎬 Video", [
            "Trim / Crop / Split",
            "Join / Merge",
            "Convert / Compress",
            "Change Resolution"
        ], "blue"),
        create_feature_panel("✨ Effects", [
            "Speed / Reverse",
            "Color Correction",
            "AI Face Blur",
            "Stabilize / Denoise"
        ], "magenta"),
        create_feature_panel("🎵 Audio & AI", [
            "AI Subtitles",
            "Extract / Remove",
            "Volume / Normalize",
            "Audio Visualizer"
        ], "green"),
        create_feature_panel("🛠️ Tools", [
            "Create Slideshow",
            "Metadata Editor",
            "GIF Maker",
            "Image Tools"
        ], "yellow"),
    ]

    console.print(Columns(panels, equal=True, expand=True))
    console.print()


def show_help_bar():
    console.print(
        "[dim][[/dim][cyan]↑↓[/cyan][dim]] Navigate  "
        "[[/dim][cyan]Enter[/cyan][dim]] Select  "
        "[[/dim][cyan]Backspace[/cyan][dim]] Back  "
        "[[/dim][cyan]Ctrl+C[/cyan][dim]] Exit[/dim]"
    )
    console.print()


def select_with_back(message, choices):
    """Select prompt with backspace support for going back."""
    back_value = None
    for choice in choices:
        if isinstance(choice, str) and "← Back" in choice:
            back_value = choice
            break

    question = questionary.select(message, choices=choices)

    if back_value:
        # Add directly to the application's existing key bindings
        kb = question.application.key_bindings

        @kb.add(Keys.Backspace, eager=True)
        @kb.add(Keys.Delete, eager=True)
        @kb.add(Keys.ControlH, eager=True)
        def handle_back(event):
            event.app.exit(result=back_value)

    return question.ask()


def video_edit_menu():
    action = select_with_back(
        "Select an edit action:",
        choices=[
            "Trim Video",
            "Crop Video (Visual)",
            "Split Video",
            "Join Multiple Videos",
            questionary.Separator(),
            "← Back"
        ]
    )

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
    action = select_with_back(
        "Select an audio action:",
        choices=[
            "Extract Audio",
            "Remove Audio",
            "Merge Audio with Video",
            "Adjust Volume",
            "Audio Fade In/Out",
            "Normalize Audio",
            questionary.Separator(),
            "← Back"
        ]
    )

    if action == "← Back" or action is None:
        return

    file_path = select_media_file(filter_type="video")
    if not file_path:
        return

    actions = {
        "Extract Audio": extract_audio,
        "Remove Audio": remove_audio,
        "Merge Audio with Video": merge_audio_video,
        "Adjust Volume": adjust_volume,
        "Audio Fade In/Out": audio_fade,
        "Normalize Audio": normalize_audio,
    }

    if action in actions:
        actions[action](file_path)


def subtitle_menu():
    file_path = select_media_file(filter_type="video")
    if not file_path:
        return
    generate_subtitles(file_path)


def video_convert_menu():
    action = select_with_back(
        "Select a convert action:",
        choices=[
            "Convert Format",
            "Compress Video",
            "Change Resolution",
            "Create GIF (Advanced)",
            questionary.Separator(),
            "← Back"
        ]
    )

    if action == "← Back" or action is None:
        return

    if action == "Create GIF (Advanced)":
        file_path = select_media_file(filter_type="video")
        if file_path:
            create_gif_advanced(file_path)
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
    action = select_with_back(
        "Select an effect:",
        choices=[
            "Change Speed",
            "Reverse Video",
            "Rotate Video",
            "Flip Video",
            "Video Fade In/Out",
            "Loop Video",
            "Color Correction",
            "Denoise Video",
            "Blur/Pixelate Region (Visual)",
            "Auto Blur Faces (AI)",
            "Add Watermark",
            "Picture-in-Picture",
            "Stabilize Video",
            "Extract Frames",
            questionary.Separator(),
            "← Back"
        ]
    )

    if action == "← Back" or action is None:
        return

    file_path = select_media_file(filter_type="video")
    if not file_path:
        return

    actions = {
        "Change Speed": change_speed,
        "Reverse Video": reverse_video,
        "Rotate Video": rotate_video,
        "Flip Video": flip_video,
        "Add Watermark": add_watermark,
        "Extract Frames": extract_frames,
        "Video Fade In/Out": video_fade,
        "Loop Video": loop_video,
        "Color Correction": color_correction,
        "Denoise Video": denoise_video,
        "Blur/Pixelate Region (Visual)": blur_region,
        "Auto Blur Faces (AI)": auto_blur_faces,
        "Picture-in-Picture": picture_in_picture,
        "Stabilize Video": stabilize_video,
    }

    if action in actions:
        actions[action](file_path)


def image_menu():
    action = select_with_back(
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
    )

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
    show_help_bar()

    while True:
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Separator("─────── Video ───────"),
                "✂️  Edit (Trim, Crop, Split, Join)",
                "🎵  Audio (Extract, Remove, Volume, Fade)",
                "🔄  Convert (Format, Compress, GIF)",
                "✨  Effects (Speed, Color, Denoise, PiP)",
                questionary.Separator("──────── AI ─────────"),
                "💬  AI Subtitles (Whisper)",
                "🔥  Brainrot Captions",
                "🧠  Background Removal",
                "👤  Auto Blur Faces",
                questionary.Separator("─────── Image ───────"),
                "🖼️  Image Tools",
                questionary.Separator("─────── Other ───────"),
                "🎬  Create Slideshow",
                "🎼  Audio Visualizer",
                "📝  Metadata Editor",
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
            console.print("[dim]Your Studio in a Shell.[/dim]")
            console.print()
            console.print("[dim italic]Built with ❤️ by [link=https://hariharen.site]Hariharen[/link][/dim italic]")
            break
        elif "Background Removal" in choice:
            file_path = select_media_file()
            if file_path:
                remove_background(file_path)
        elif "Brainrot" in choice:
            file_path = select_media_file(filter_type="video")
            if file_path:
                brainrot_captions(file_path)
        elif "Metadata" in choice:
            file_path = select_media_file()
            if file_path:
                metadata_editor(file_path)
        elif "Visualizer" in choice:
            file_path = select_media_file()
            if file_path:
                audio_visualizer(file_path)
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
        elif "Slideshow" in choice:
            create_slideshow()
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
