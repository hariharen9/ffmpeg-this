# 🎬 ffmPEG-this

<p align="center">
    <a href="https://pypi.org/project/peg-this/">
        <img src="https://img.shields.io/pypi/v/peg_this?color=blue&label=version" alt="PyPI Version">
    </a>
    <a href="https://pypi.org/project/peg-this/">
        <img src="https://img.shields.io/pypi/pyversions/peg_this.svg" alt="PyPI Python Versions">
    </a>
    <a href="https://github.com/hariharen9/ffmpeg-this/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/hariharen9/ffmpeg-this" alt="License">
    </a>
    <a href="https://pepy.tech/project/peg-this">
        <img src="https://static.pepy.tech/badge/peg-this" alt="Downloads">
    </a>
</p>

> Your Video editor within CLI 🚀

A powerful and user-friendly batch script for converting, manipulating, and inspecting media files using the power of FFmpeg. This script provides a simple command-line menu to perform common audio and video tasks without needing to memorize complex FFmpeg commands.


<p align="center">
    <img src="/assets/peg.gif" width="720">
</p>


## ✨ Features

- **Inspect Media Properties**: View detailed information about video and audio streams, including codecs, resolution, frame rate, bitrates, and more.
- **Convert & Transcode**: Convert videos and audio to a wide range of popular formats (MP4, MKV, WebM, MP3, FLAC, WAV, GIF) with simple quality presets.
- **Join Videos (Concatenate)**: Combine two or more videos into a single file. The tool automatically handles differences in resolution and audio sample rates for a seamless join.
- **Trim (Cut) Videos**: Easily cut a video to a specific start and end time without re-encoding for fast, lossless clips.
- **Visually Crop Videos**: An interactive tool that shows you a frame of the video, allowing you to click and drag to select the exact area you want to crop.
- **Extract Audio**: Rip the audio track from any video file into MP3, FLAC, or WAV.
- **Remove Audio**: Create a silent version of your video by stripping out all audio streams.
- **Batch Conversion**: Convert all media files in the current directory to a specified format in one go.
- **CLI Interface**: A user-friendly command-line interface that makes it easy to perform common tasks and navigate the tool's features.


## 🚀 Usage
### Prerequisite: Install FFmpeg

> [NOTE]
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

There are three ways to use `peg_this`:

### 1. Pip Install (Recommended)
This is the easiest way to get started. This will install the tool and all its dependencies.

```bash
pip install peg_this
```

Once installed, you can run the tool from your terminal:

```bash
peg_this
```

### 2. Download from Release
If you prefer not to install the package, you can download a pre-built executable from the [Releases](https://github.com/hariharen9/ffmpeg-this/releases/latest) page.

1.  Download the executable for your operating system (Windows, macOS, or Linux).
2.  Place it in a directory with your media files.
3.  Run the executable directly from your terminal.

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
    python -m src.peg_this.peg_this
    ```

## 📈 Star History

<p align="center">
  <a href="https://star-history.com/#hariharen9/ffmpeg-this&Date">
    <img src="https://api.star-history.com/svg?repos=hariharen9/ffmpeg-this&type=Date" alt="Star History Chart">
  </a>
</p>

## ✨ Sponsor

<p align="center">
    <a href="https://github.com/sponsors/hariharen9">
        <img src="https://img.shields.io/github/sponsors/hariharen9?style=for-the-badge&logo=github&color=white" alt="GitHub Sponsors">
    </a>
    <a href="https://www.buymeacoffee.com/hariharen">
        <img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee">
    </a>
</p>

## 👥 Contributors

<a href="https://github.com/hariharen9/ffmpeg-this/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=hariharen9/ffmpeg-this" />
</a>

## 🤝 Contributing

Contributions are welcome! Please see the [Contributing Guidelines](CONTRIBUTING.md) for more information.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

<p align="center">
    <h2>Made with ❤️ by <a href="https://hariharen9.site">Hariharen</a></h2>
</p>