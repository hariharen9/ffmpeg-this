import sys
import subprocess
import shutil
from pathlib import Path

import questionary
from rich.console import Console

from peg_this.utils.validation import validate_input_file, press_continue, check_file_exists

console = Console()


def check_demucs_installed():
    """Check if demucs is installed and importable."""
    try:
        import demucs
        return True
    except ImportError:
        return False


def separate_stems(file_path):
    if not validate_input_file(file_path):
        press_continue()
        return

    # Check for Demucs installation
    if not check_demucs_installed():
        console.print("[bold red]Error: Demucs is not installed.[/bold red]")
        console.print("[yellow]Install with: pip install peg_this[demucs][/yellow]")
        console.print("[dim]Note: This is ~1.5GB as it includes PyTorch.[/dim]")
        press_continue()
        return

    console.print(f"[bold cyan]AI Music Separation[/bold cyan]")
    console.print(f"[dim]File: {Path(file_path).name}[/dim]")

    # Select Separation Mode
    mode = questionary.select(
        "Select Separation Mode:",
        choices=[
            "Karaoke / Instrumental (2 Stems: Vocals + Backing)",
            "Standard Band (4 Stems: Vocals, Drums, Bass, Other)",
            "Advanced (6 Stems: + Guitar, Piano)",
            "← Back"
        ]
    ).ask()

    if mode == "← Back" or mode is None:
        return

    # Select Output Format
    fmt = questionary.select(
        "Select Output Format:",
        choices=[
            "MP3 (320kbps) - Recommended",
            "WAV (Lossless) - Large Files",
            "FLAC (Lossless) - Compressed"
        ]
    ).ask()

    if fmt is None:
        return

    # Construct Demucs Arguments
    cmd = [sys.executable, "-m", "demucs.separate", "-o", "separated", str(file_path)]

    model_name = "htdemucs"  # Hybrid Transformer (Default, Fast, Good Quality)

    if "2 Stems" in mode:
        cmd.extend(["-n", model_name, "--two-stems", "vocals"])
    elif "6 Stems" in mode:
        model_name = "htdemucs_6s"
        cmd.extend(["-n", model_name])
    else:  # Standard 4 Stems
        cmd.extend(["-n", model_name])

    if "MP3" in fmt:
        cmd.extend(["--mp3", "--mp3-bitrate", "320"])
    elif "FLAC" in fmt:
        cmd.append("--flac")
    # WAV is default for demucs, no flag needed

    console.print("\n[bold yellow]🚀 Starting AI Separation...[/bold yellow]")
    console.print("[dim]This runs on your CPU/GPU. First run will download the model (~100MB - 1GB).[/dim]")
    console.print("[dim]Please wait, this may take a few minutes...[/dim]\n")

    try:
        # Run Demucs
        with console.status("[bold green]Processing audio...[/bold green]", spinner="dots"):
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

        if result.returncode == 0:
            # Success
            # Calculate expected output path
            # Demucs structure: separated/model_name/track_name/
            track_name = Path(file_path).stem
            output_dir = Path("separated") / model_name / track_name

            console.print(f"\n[bold green]✅ Separation Complete![/bold green]")
            if output_dir.exists():
                console.print(f"Output saved to: [bold underline]{output_dir.absolute()}[/bold underline]")
                # List files
                files = list(output_dir.glob("*"))
                console.print("\n[dim]Generated Stems:[/dim]")
                for f in files:
                    console.print(f" - {f.name}")
            else:
                console.print(f"[yellow]Note: Could not verify output directory, check 'separated/{model_name}' folder.[/yellow]")
                console.print(f"[dim]Demucs output:\n{result.stdout}[/dim]")

        else:
            # Failure
            console.print("[bold red]❌ Separation Failed.[/bold red]")
            console.print(f"[red]Error output:[/red]\n{result.stderr}")
            if "torch" in result.stderr:
                console.print("\n[yellow]Hint: This error often relates to PyTorch. Ensure your system meets requirements.[/yellow]")

    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")

    press_continue()
