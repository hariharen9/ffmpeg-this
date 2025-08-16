import os
import sys
import logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import questionary
from rich.console import Console

from peg_this.features.audio import extract_audio, remove_audio
from peg_this.features.batch import batch_convert
from peg_this.features.convert import convert_file
from peg_this.features.crop import crop_video
from peg_this.features.inspect import inspect_file
from peg_this.features.join import join_videos
from peg_this.features.trim import trim_video
from peg_this.utils.ffmpeg_utils import check_ffmpeg_ffprobe
from peg_this.utils.ui_utils import select_media_file

# --- Global Configuration ---
# Configure logging
log_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ffmpeg_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w') # Overwrite log on each run
    ]
)

# Initialize Rich Console
console = Console()
# --- End Global Configuration ---


def action_menu(file_path):
    """Display the menu of actions for a selected file."""
    while True:
        console.rule(f"[bold]Actions for: {os.path.basename(file_path)}[/bold]")
        action = questionary.select(
            "Choose an action:",
            choices=[
                "Inspect File Details",
                "Convert",
                "Trim Video",
                "Crop Video (Visual)",
                "Extract Audio",
                "Remove Audio",
                questionary.Separator(),
                "Back to File List"
            ],
            use_indicator=True
        ).ask()

        if action is None or action == "Back to File List":
            break

        actions = {
            "Inspect File Details": inspect_file,
            "Convert": convert_file,
            "Trim Video": trim_video,
            "Crop Video (Visual)": crop_video,
            "Extract Audio": extract_audio,
            "Remove Audio": remove_audio,
        }
        # Ensure we have a valid action before calling
        if action in actions:
            actions[action](file_path)


def main_menu():
    """Display the main menu."""
    check_ffmpeg_ffprobe()
    while True:
        console.rule("[bold magenta]ffmPEG-this[/bold magenta]")
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Process a Single Media File",
                "Join Multiple Videos",
                "Batch Convert All Media in Directory",
                "Exit"
            ],
            use_indicator=True
        ).ask()

        if choice is None or choice == "Exit":
            console.print("[bold]Goodbye![/bold]")
            console.print("\n[italic cyan]Built with ❤️ by Hariharen[/italic cyan]")
            break
        elif choice == "Process a Single Media File":
            selected_file = select_media_file()
            if selected_file:
                action_menu(selected_file)
        elif choice == "Join Multiple Videos":
            join_videos()
        elif choice == "Batch Convert All Media in Directory":
            batch_convert()


def main():
    """Main entry point for the application script."""
    try:
        main_menu()
    except (KeyboardInterrupt, EOFError):
        logging.info("Operation cancelled by user.")
        console.print("[bold]Operation cancelled. Goodbye![/bold]")
    except Exception as e:
        logging.exception("An unexpected error occurred.")
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        console.print(f"Details have been logged to {log_file}")

if __name__ == "__main__":
    main()