# 🎬 ffmPEG-this

> Your Video editor within CLI 🚀

A powerful and user-friendly batch script for converting, manipulating, and inspecting media files using the power of FFmpeg. This script provides a simple command-line menu to perform common audio and video tasks without needing to memorize complex FFmpeg commands.


<img src="/assets/peg.gif" width="720">


## ✨ Features

- **Inspect Media Properties**: View detailed information about video and audio streams, including codecs, resolution, frame rate, bitrates, and more.
- **Convert & Transcode**: Convert videos and audio to a wide range of popular formats (MP4, MKV, WebM, MP3, FLAC, WAV, GIF) with simple quality presets.
- **Join Videos (Concatenate)**: Combine two or more videos into a single file. The tool automatically handles differences in resolution and audio sample rates for a seamless join.
- **Trim (Cut) Videos**: Easily cut a video to a specific start and end time without re-encoding for fast, lossless clips.
- **Visually Crop Videos**: An interactive tool that shows you a frame of the video, allowing you to click and drag to select the exact area you want to crop.
- **Extract Audio**: Rip the audio track from any video file into MP3, FLAC, or WAV.
- **Remove Audio**: Create a silent version of your video by stripping out all audio streams.
- **Batch Conversion**: Convert all media files in the current directory to a specified format in one go.


## 🚀 Usage
### Prerequisite: Install FFmpeg

> `peg_this` uses a library called `ffmpeg-python` which acts as a controller for the main FFmpeg program. It does not include FFmpeg itself. Therefore, you must have FFmpeg installed on your system and available in your terminal's PATH.

For **macOS** users, the easiest way to install it is with [Homebrew](https://brew.sh/):
```bash
brew install ffmpeg
```

For **Windows** users, you can use a package manager like [Chocolatey](https://chocolatey.org/) or [Scoop](https://scoop.sh/):
```bash
# Using Chocolatey
choco install ffmpeg

# Using Scoop
scoop install ffmpeg
```

For other systems, please see the official download page: **[ffmpeg.org/download.html](https://ffmpeg.org/download.html)**

There are ***three*** ways to use `peg_this`:

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