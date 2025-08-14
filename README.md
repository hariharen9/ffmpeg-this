# 🎬 ffmPEG-this

A powerful and user-friendly batch script for converting, manipulating, and inspecting media files using the power of FFmpeg. This script provides a simple command-line menu to perform common audio and video tasks without needing to memorize complex FFmpeg commands.

## ✨ Features

- **Action-Oriented Menu:** Select a file, then choose from a list of available actions.
- **File Inspection:** View detailed information about a media file, including resolution, duration, size, and stream details.
- **Lossless Conversion:** Change a file's container format (e.g., **MKV to MP4, , MP4 to GIF** etc.) without re-encoding, preserving the original quality.
- **Lossy Conversion:** Re-encode video to reduce file size, with simple quality presets.
- **Video Trimming:** Cut a video by specifying a start and end time.
- **Audio Extraction:** Extract the audio from a video file into formats like MP3, FLAC, or WAV.
- **Audio Removal:** Create a silent version of a video by removing its audio track.
- **Batch Conversion:** Convert all video files in the directory to a specific format in one go.

## 🚀 Usage

There are three ways to use `peg_this`:

### 1. Pip Install (Recommended)

This is the easiest way to get started. This will install the tool and all its dependencies, including `ffmpeg`.

```bash
pip install peg_this
```

Once installed, you can run the tool from your terminal:

```bash
peg_this
```

### 2. Download from Release

If you don't want to install the package, you can download a pre-built executable from the [Releases](https://github.com/hariharen9/ffmpeg-this/releases/latest) page.

1.  Download the executable for your operating system (Windows, macOS, or Linux).
2.  Place the downloaded file in a directory with your media files.
3.  Run the executable directly from your terminal or command prompt.

### 3. Run from Source

If you want to run the script directly from the source code:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/hariharen9/ffmpeg-this.git
    cd ffmpeg-this
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the script:**
    ```bash
    python src/peg_this/peg_this.py
    ```

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.