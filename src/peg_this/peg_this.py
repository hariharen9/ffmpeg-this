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
from peg_this.features.convert import convert_file, convert_image, resize_image, rotate_image, flip_image, adjust_image_colors, blur_sharpen_image, image_effects, add_image_border, compress_image, add_image_text
from peg_this.features.crop import crop_video, crop_image
from peg_this.features.effects import add_watermark, merge_audio_video, video_fade, loop_video, color_correction, denoise_video, picture_in_picture, blur_region, auto_blur_faces, audio_visualizer, rotate_video, flip_video, remove_background
from peg_this.features.frames import extract_frames, split_video
from peg_this.features.inspect import inspect_file
from peg_this.features.join import join_videos
from peg_this.features.speed import change_speed, reverse_video, smooth_slow_motion, change_fps
from peg_this.features.subtitle import generate_subtitles, brainrot_captions
from peg_this.features.dubbing import auto_dub
from peg_this.features.trim import trim_video
from peg_this.features.advanced import create_slideshow, metadata_editor, stabilize_video, create_gif_advanced
from peg_this.features.music_separation import separate_stems
from peg_this.features.upscale import upscale_video
from peg_this.features.download import download_media
from peg_this.features.reframe import smart_reframe
from peg_this.settings import settings_menu
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
VERSION = "5.1.0"

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
    console.print(Align.center("[dim italic]Your Studio in Shell[/dim italic]"))
    console.print()

    # Feature panels
    panels = [
        create_feature_panel("🎬 Video", [
            "Trim / Crop / Split",
            "Join / Merge",
            "Convert / Compress",
            "Effects / Filters"
        ], "blue"),
        create_feature_panel("🖼️ Image", [
            "Resize / Rotate / Crop",
            "Colors / Blur / Effects",
            "Border / Text",
            "Compress / Convert"
        ], "cyan"),
        create_feature_panel("🎵 Audio", [
            "Extract / Remove",
            "Volume / Normalize",
            "Fade / Convert",
            "Visualizer"
        ], "green"),
        create_feature_panel("🤖 AI", [
            "Subtitles / Captions",
            "Music Stem Separation",
            "Background Removal",
            "Upscaling / Face Blur"
        ], "magenta"),
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


# =============================================================================
# VIDEO MENUS
# =============================================================================

def video_edit_menu():
    action = select_with_back(
        "Select an edit action:",
        choices=[
            "Trim Video",
            "Crop Video (Visual)",
            "Split Video",
            "Join Multiple Videos",
            "Extract Frames",
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
        "Extract Frames": extract_frames,
    }

    if action in actions:
        actions[action](file_path)


def video_convert_menu():
    action = select_with_back(
        "Select a convert action:",
        choices=[
            "Convert Format",
            "Compress Video",
            "Change Resolution",
            "Change FPS",
            "Create GIF",
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
        "Convert Format": convert_file,
        "Compress Video": compress_video,
        "Change Resolution": change_resolution,
        "Change FPS": change_fps,
        "Create GIF": create_gif_advanced,
    }

    if action in actions:
        actions[action](file_path)


def video_effects_menu():
    action = select_with_back(
        "Select an effect:",
        choices=[
            "Change Speed",
            "Smooth Slow Motion (Optical Flow)",
            "Reverse Video",
            "Rotate / Flip",
            "Video Fade In/Out",
            "Loop Video",
            "Color Correction",
            "Denoise Video",
            "Blur/Pixelate Region (Visual)",
            "Add Watermark",
            "Picture-in-Picture",
            "Stabilize Video",
            questionary.Separator(),
            "← Back"
        ]
    )

    if action == "← Back" or action is None:
        return

    # Handle Rotate/Flip submenu
    if action == "Rotate / Flip":
        sub_action = select_with_back(
            "Select transform:",
            choices=[
                "Rotate Video",
                "Flip Video",
                questionary.Separator(),
                "← Back"
            ]
        )
        if sub_action == "← Back" or sub_action is None:
            return
        file_path = select_media_file(filter_type="video")
        if not file_path:
            return
        if sub_action == "Rotate Video":
            rotate_video(file_path)
        else:
            flip_video(file_path)
        return

    file_path = select_media_file(filter_type="video")
    if not file_path:
        return

    actions = {
        "Change Speed": change_speed,
        "Smooth Slow Motion (Optical Flow)": smooth_slow_motion,
        "Reverse Video": reverse_video,
        "Add Watermark": add_watermark,
        "Video Fade In/Out": video_fade,
        "Loop Video": loop_video,
        "Color Correction": color_correction,
        "Denoise Video": denoise_video,
        "Blur/Pixelate Region (Visual)": blur_region,
        "Picture-in-Picture": picture_in_picture,
        "Stabilize Video": stabilize_video,
    }

    if action in actions:
        actions[action](file_path)


# =============================================================================
# IMAGE MENUS
# =============================================================================

def image_transform_menu():
    action = select_with_back(
        "Select a transform action:",
        choices=[
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
        "Resize": resize_image,
        "Rotate": rotate_image,
        "Flip": flip_image,
        "Crop (Visual)": crop_image,
    }

    if action in actions:
        actions[action](file_path)


def image_adjust_menu():
    action = select_with_back(
        "Select an adjustment:",
        choices=[
            "Adjust Colors (Brightness/Contrast/Saturation)",
            "Blur / Sharpen",
            "Effects (Grayscale/Sepia/Invert)",
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
        "Adjust Colors (Brightness/Contrast/Saturation)": adjust_image_colors,
        "Blur / Sharpen": blur_sharpen_image,
        "Effects (Grayscale/Sepia/Invert)": image_effects,
    }

    if action in actions:
        actions[action](file_path)


def image_add_menu():
    action = select_with_back(
        "Select what to add:",
        choices=[
            "Add Border",
            "Add Text / Caption",
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
        "Add Border": add_image_border,
        "Add Text / Caption": add_image_text,
    }

    if action in actions:
        actions[action](file_path)


def image_convert_menu():
    action = select_with_back(
        "Select a convert action:",
        choices=[
            "Convert Format",
            "Compress / Optimize",
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
        "Compress / Optimize": compress_image,
    }

    if action in actions:
        actions[action](file_path)


# =============================================================================
# AUDIO MENUS
# =============================================================================

def audio_edit_menu():
    action = select_with_back(
        "Select an edit action:",
        choices=[
            "Extract Audio from Video",
            "Remove Audio from Video",
            "Merge Audio with Video",
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
        "Extract Audio from Video": extract_audio,
        "Remove Audio from Video": remove_audio,
        "Merge Audio with Video": merge_audio_video,
    }

    if action in actions:
        actions[action](file_path)


def audio_adjust_menu():
    action = select_with_back(
        "Select an adjustment:",
        choices=[
            "Adjust Volume",
            "Audio Fade In/Out",
            "Normalize Audio",
            questionary.Separator(),
            "← Back"
        ]
    )

    if action == "← Back" or action is None:
        return

    # These work on both video and audio files
    file_path = select_media_file()
    if not file_path:
        return

    actions = {
        "Adjust Volume": adjust_volume,
        "Audio Fade In/Out": audio_fade,
        "Normalize Audio": normalize_audio,
    }

    if action in actions:
        actions[action](file_path)


def audio_convert_menu():
    action = select_with_back(
        "Select a convert action:",
        choices=[
            "Convert Audio Format",
            questionary.Separator(),
            "← Back"
        ]
    )

    if action == "← Back" or action is None:
        return

    file_path = select_media_file()
    if not file_path:
        return

    if action == "Convert Audio Format":
        convert_file(file_path)


# =============================================================================
# OTHER MENUS
# =============================================================================

def inspect_menu():
    file_path = select_media_file()
    if file_path:
        inspect_file(file_path)


# =============================================================================
# MAIN MENU
# =============================================================================

def main_menu():
    check_ffmpeg_ffprobe()
    show_landing()
    show_help_bar()

    while True:
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Separator("─────── Video ───────"),
                "✂️  Edit (Trim, Crop, Split, Join, Frames)",
                "🔄  Convert (Format, Compress, Resolution, FPS, GIF)",
                "✨  Effects (Speed, Color, Denoise, Watermark)",
                questionary.Separator("─────── Image ───────"),
                "🖼️  Transform (Resize, Rotate, Flip, Crop)",
                "🎨  Adjust (Colors, Blur, Effects)",
                "✏️  Add (Border, Text)",
                "📁  Convert (Format, Compress)",
                questionary.Separator("─────── Audio ───────"),
                "🎵  Edit (Extract, Remove, Merge)",
                "🔊  Adjust (Volume, Fade, Normalize)",
                "💿  Convert (Format)",
                "🎼  Visualizer",
                questionary.Separator("──────── AI ─────────"),
                "💬  Subtitles (Whisper)",
                "🔥  Brainrot Captions",
                "🎙️  Auto-Dubbing",
                "🎹  Separate Music Stems (Demucs)",
                "🧠  Background Removal",
                "👤  Auto Blur Faces",
                "🚀  Video Upscaling",
                "📐  Smart Reframe (AI Crop)",
                questionary.Separator("─────── Other ───────"),
                "🌐  Download (yt-dlp)",
                "🎬  Create Slideshow",
                "📝  Metadata Editor",
                "📦  Batch Convert",
                "🔍  Inspect File",
                "⚙️  Settings",
                questionary.Separator(),
                "👋  Exit"
            ],
            use_indicator=True
        ).ask()

        if choice is None or "Exit" in choice:
            console.print()
            console.print("[bold magenta]Thanks for using peg_this![/bold magenta]")
            console.print("[dim]Your Studio in a (nut)Shell 😉.[/dim]")
            console.print()
            console.print("[dim italic]Built with ❤️ by [link=https://hariharen.site]Hariharen[/link][/dim italic]")
            break

        # Dispatch table: (substring_key, handler, file_filter)
        # file_filter=None  → call handler() directly (submenus, no-arg actions)
        # file_filter="video"/"image" → select file with filter, call handler(file_path)
        # file_filter="any" → select file without filter, call handler(file_path)
        dispatch = [
            # VIDEO
            ("Edit (Trim",                                video_edit_menu,    None),
            ("Convert (Format, Compress, Resolution, FPS", video_convert_menu, None),
            ("Effects (Speed",                            video_effects_menu, None),
            # IMAGE
            ("Transform (Resize",                         image_transform_menu, None),
            ("Adjust (Colors",                            image_adjust_menu,  None),
            ("Add (Border",                               image_add_menu,     None),
            ("Convert (Format, Compress)",                image_convert_menu, None),
            # AUDIO
            ("Edit (Extract",                             audio_edit_menu,    None),
            ("Adjust (Volume",                            audio_adjust_menu,  None),
            ("Convert (Format)",                          audio_convert_menu, None),
            ("Visualizer",                                audio_visualizer,   "any"),
            # AI
            ("Subtitles (Whisper)",                       generate_subtitles, "video"),
            ("Brainrot",                                  brainrot_captions,  "video"),
            ("Auto-Dubbing",                              auto_dub,           "video"),
            ("Separate Music Stems",                      separate_stems,     "any"),
            ("Background Removal",                        remove_background,  "any"),
            ("Blur Faces",                                auto_blur_faces,    "video"),
            ("Upscaling",                                 upscale_video,      "video"),
            ("Smart Reframe",                            smart_reframe,      "video"),
            # OTHER
            ("Download",                                 download_media,     None),
            ("Slideshow",                                 create_slideshow,   None),
            ("Metadata",                                  metadata_editor,    "any"),
            ("Batch",                                     batch_convert,      None),
            ("Inspect",                                   inspect_menu,       None),
            ("Settings",                                  settings_menu,      None),
        ]

        for key, handler, file_filter in dispatch:
            if key in choice:
                if file_filter is None:
                    handler()
                else:
                    kw = {"filter_type": file_filter} if file_filter != "any" else {}
                    file_path = select_media_file(**kw)
                    if file_path:
                        handler(file_path)
                break


import argparse

def main():
    parser = argparse.ArgumentParser(description="FFMPEG-this: Your Studio in a Shell")
    parser.add_argument("--gui", action="store_true", help="Launch the experimental Graphical User Interface")
    parser.add_argument("-d", "--download", metavar="URL", help="Download a video directly from a URL")
    parser.add_argument("-dy", "--download-yolo", metavar="URL", help="Download best quality MP4 instantly, no prompts")
    args, unknown = parser.parse_known_args()

    if args.gui:
        try:
            from peg_this.ui.app import run_gui
            run_gui()
        except ImportError as e:
            console.print(f"[bold red]Failed to launch GUI: {e}[/bold red]")
            console.print("[yellow]Ensure you have 'dearpygui' installed: pip install dearpygui[/yellow]")
            sys.exit(1)
        except Exception as e:
            logging.exception("GUI crashed.")
            console.print(f"[bold red]GUI Error: {e}[/bold red]")
            sys.exit(1)
        return

    if args.download:
        try:
            from peg_this.features.download import download_url
            download_url(args.download)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold]Operation cancelled. Goodbye![/bold]")
        except Exception as e:
            logging.exception("Download failed.")
            console.print(f"[bold red]Download error: {e}[/bold red]")
        return

    if args.download_yolo:
        try:
            from peg_this.features.download import download_url_quick
            download_url_quick(args.download_yolo)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold]Operation cancelled. Goodbye![/bold]")
        except Exception as e:
            logging.exception("Download failed.")
            console.print(f"[bold red]Download error: {e}[/bold red]")
        return

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
