# 🎬 ffmPEG-this

A powerful and user-friendly batch script for converting, manipulating, and inspecting media files using the power of FFmpeg. This script provides a simple command-line menu to perform common audio and video tasks without needing to memorize complex FFmpeg commands.

## ✨ Features

- **Action-Oriented Menu:** Select a file, then choose from a list of available actions.
- **File Inspection:** View detailed information about a media file, including resolution, duration, size, and stream details.
- **Lossless Conversion:** Change a file's container format (e.g., MKV to MP4) without re-encoding, preserving the original quality.
- **Lossy Conversion:** Re-encode video to reduce file size, with simple quality presets.
- **Video Trimming:** Cut a video by specifying a start and end time.
- **Audio Extraction:** Extract the audio from a video file into formats like MP3, FLAC, or WAV.
- **Audio Removal:** Create a silent version of a video by removing its audio track.
- **Batch Conversion:** Convert all video files in the directory to a specific format in one go.

## 🚀 Getting Started

### Prerequisites

- **FFmpeg**: Must be installed and accessible in your system's PATH, or the `ffmpeg` and `ffprobe` executables must be placed in the same directory as the converter.

### Installation

1.  Go to the [**Releases**](https://github.com/hariharen9/ffmpeg-this/releases/latest) page.
2.  Download the executable for your operating system (Windows, macOS, or Linux).
3.  Place the downloaded file in a directory with your media files.
4.  Run the executable directly from your terminal or command prompt.

### Easiest Way to Get Started (Recommended for Most Users)

For the quickest and most straightforward experience, especially if you're new to command-line tools or prefer a direct approach:

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/hariharen9/ffmpeg-this.git
    cd ffmpeg-this
    ```
2.  **Place Your Media Files:** Copy or move the video/audio files you wish to process directly into this `ffmpeg-this` directory.
3.  **Run the Python Script (Cross-Platform):**
    ```bash
    python peg_this.py
    ```
    This will launch the interactive menu, allowing you to select files and perform operations with a modern, user-friendly interface.

4.  **Alternatively, Use the Batch Script (Windows Only):**
    If you are on Windows and prefer a simpler, direct executable feel without needing to explicitly run Python:
    ```bash
    peg_this.bat
    ```
    This will also launch an interactive menu, providing similar functionalities directly from the batch file.

## 💻 Usage

Run the application from your terminal to launch the interactive menu.

```
$ ./ffmpeg-this
```

You will be greeted with the main menu, where you can select a file to process or perform a batch conversion.

```
==============================================
         ffmpeg-this
==============================================

1. Select a Media File to Process
2. Batch Convert All Videos to a Format
3. Exit
```

After selecting a file, a rich, interactive menu will display detailed information and offer a variety of actions:

```
===============================================
     Actions for: your_video.mp4
===============================================

1. Inspect File Details
2. Convert (Lossless)
3. Convert (Smaller File Size)
4. Trim Video
5. Extract Audio
6. Remove Audio
...
```

## 🛠️ Building executable from Source

If you prefer to run the script directly or build it yourself:

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
    python peg_this.py
    ```
4.  **(Optional) Build the executable:**
    To create the standalone executable, use PyInstaller:
    ```bash
    pip install pyinstaller
    pyinstaller --onefile --name "ffmpeg-this" peg_this.py
    ```


## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.