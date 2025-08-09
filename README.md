# 🎬 AV Converter

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

- [FFmpeg](https://ffmpeg.org/download.html) must be downloaded and the executables (`ffmpeg.exe`, `ffprobe.exe`) must be in the same directory as the script.

### Installation

1.  Download the `enhanced_converter.bat` script from the [latest release](https://github.com/hariharen9/av-converter/releases/latest).
2.  Place the script in the same directory as `ffmpeg.exe` and `ffprobe.exe`.
3.  Add any media files you want to process into the same directory.
4.  Run `enhanced_converter.bat` by double-clicking it or by running it from the command line.

## 💻 Usage

Once the script is running, you will be presented with a main menu.

```
===============================================
         Enhanced Media Converter
===============================================

1. Select a Media File to Process
2. Batch Convert All Videos to a Format
3. Exit
```

Simply choose an option and follow the on-screen prompts. When you select a file, you'll see the action menu:

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

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
