import json
import os
import subprocess
from pathlib import Path
from rich.console import Console
import questionary

console = Console()

CONFIG_FILE = Path.home() / ".peg_this_config.json"

DEFAULT_CONFIG = {
    "video_encoder": "libx264",  # Default CPU encoder
    "video_encoder_friendly": "CPU (libx264)",
}

# Encoder Definitions
# Maps detection strings to internal names and friendly names
ENCODER_MAP = {
    "libx264": "CPU (libx264 - Best Compatibility)",
    "h264_nvenc": "NVIDIA GPU (h264_nvenc)",
    "h264_videotoolbox": "macOS GPU (h264_videotoolbox)",
    "h264_amf": "AMD GPU (h264_amf)",
    "h264_qsv": "Intel QuickSync (h264_qsv)"
}

class Settings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    self.config = json.load(f)
            except Exception:
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()
            self._save_config()

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            console.print(f"[red]Failed to save settings: {e}[/red]")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self._save_config()

    def detect_encoders(self):
        """Run ffmpeg -encoders to find available hardware accelerators."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-encoders"],
                capture_output=True,
                text=True
            )
            output = result.stdout

            available = []

            # Always available (software)
            available.append("libx264")

            if "nvenc" in output:
                # Check specific codec existence
                if "h264_nvenc" in output:
                    available.append("h264_nvenc")

            if "videotoolbox" in output:
                if "h264_videotoolbox" in output:
                    available.append("h264_videotoolbox")

            if "amf" in output:
                if "h264_amf" in output:
                    available.append("h264_amf")

            if "qsv" in output:
                if "h264_qsv" in output:
                    available.append("h264_qsv")

            return available

        except Exception:
            # Fallback to just CPU if check fails
            return ["libx264"]

    def get_encoding_args(self, quality="medium", crf=23):
        """
        Returns a dictionary of ffmpeg arguments based on the selected encoder.
        Abstraction layer to handle different preset names and quality flags.

        quality: 'high', 'medium', 'low'
        crf: approximate visual quality (lower is better, standard is 23)
        """
        encoder = self.config.get("video_encoder", "libx264")

        args = {"c:v": encoder}

        # CPU (Standard)
        if encoder == "libx264":
            args["crf"] = str(crf)
            if quality == "high":
                args["preset"] = "slow"
            elif quality == "low":
                args["preset"] = "veryfast"
            else:
                args["preset"] = "medium"

        # NVIDIA GPU (NVENC)
        elif encoder == "h264_nvenc":
            # NVENC uses -cq for VBR quality control (similar to CRF)
            # Presets: p1 (fastest) to p7 (slowest/best)
            args["rc"] = "vbr"
            args["cq"] = str(crf)

            if quality == "high":
                args["preset"] = "p6"
            elif quality == "low":
                args["preset"] = "p2"
            else:
                args["preset"] = "p4" # Default/Medium

        # macOS GPU (VideoToolbox)
        elif encoder == "h264_videotoolbox":
            # VideoToolbox quality usually 0-100.
            # CRF 18 ~ Q 65, CRF 23 ~ Q 50, CRF 28 ~ Q 40 roughly
            q_val = 50
            if crf <= 18: q_val = 65
            elif crf >= 28: q_val = 40
            else:
                # Linear interpolate roughly: 23->50
                q_val = int(50 + (23 - crf) * 3)

            args["q:v"] = str(q_val)
            # VideoToolbox doesn't have standard 'presets' like x264

        # AMD GPU (AMF)
        elif encoder == "h264_amf":
            args["usage"] = "transcoding"
            args["rc"] = "cqp" # Constant Quantization Parameter
            args["qp_i"] = str(crf)
            args["qp_p"] = str(crf)
            if quality == "high":
                args["quality"] = "quality"
            elif quality == "low":
                args["quality"] = "speed"
            else:
                args["quality"] = "balanced"

        # Intel QuickSync (QSV)
        elif encoder == "h264_qsv":
            args["global_quality"] = str(crf) # Lookahead needs to be enabled for this often
            if quality == "high":
                args["preset"] = "veryslow"
            elif quality == "low":
                args["preset"] = "veryfast"
            else:
                args["preset"] = "medium"

        else:
            # Fallback for unknown
            args["c:v"] = "libx264"
            args["crf"] = "23"
            args["preset"] = "medium"

        return args

    def get_encoder_list_args(self, quality="medium", crf=23):
        """Returns encoding args as a list for subprocess calls (e.g., ['-c:v', '...'])."""
        args_dict = self.get_encoding_args(quality, crf)
        args_list = []
        for k, v in args_dict.items():
            args_list.append(f"-{k}")
            args_list.append(str(v))
        return args_list


def settings_menu():
    settings = Settings()

    while True:
        current_enc = settings.get("video_encoder_friendly")

        choice = questionary.select(
            "Settings",
            choices=[
                f"Video Encoder: {current_enc}",
                "Scan for Hardware Encoders",
                questionary.Separator(),
                "← Back"
            ]
        ).ask()

        if choice == "← Back" or choice is None:
            break

        if choice == "Scan for Hardware Encoders":
            with console.status("Scanning ffmpeg encoders..."):
                encoders = settings.detect_encoders()

            console.print(f"\n[green]Found {len(encoders)} compatible encoders.[/green]")

            enc_choices = []
            for enc in encoders:
                label = ENCODER_MAP.get(enc, enc)
                enc_choices.append(questionary.Choice(title=label, value=enc))

            selected_enc = questionary.select(
                "Select preferred video encoder:",
                choices=enc_choices
            ).ask()

            if selected_enc:
                friendly_name = ENCODER_MAP.get(selected_enc, selected_enc)
                settings.set("video_encoder", selected_enc)
                settings.set("video_encoder_friendly", friendly_name)
                console.print(f"[bold green]Encoder set to: {friendly_name}[/bold green]")

        elif choice.startswith("Video Encoder"):
            # Quick select existing known ones without rescanning
            encoders = settings.detect_encoders() # Fast enough usually
            enc_choices = []
            for enc in encoders:
                label = ENCODER_MAP.get(enc, enc)
                enc_choices.append(questionary.Choice(title=label, value=enc))

            selected_enc = questionary.select(
                "Select preferred video encoder:",
                choices=enc_choices
            ).ask()

            if selected_enc:
                friendly_name = ENCODER_MAP.get(selected_enc, selected_enc)
                settings.set("video_encoder", selected_enc)
                settings.set("video_encoder_friendly", friendly_name)
