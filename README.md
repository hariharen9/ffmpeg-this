<h1 align="center">FFm<u><i>PEG</i></u>-this</h1>

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

<p align="center"><b>Your Editor within CLI</b></p>

A powerful and user-friendly Python CLI tool for converting, manipulating, and inspecting media files using the power of FFmpeg. This tool provides a simple command-line menu to perform common audio and video tasks without needing to memorize complex FFmpeg commands.

<p align="center">
    <img src="/assets/peg.gif" width="720">
</p>

## Features at a Glance

| Category | Feature | Description |
|----------|---------|-------------|
| **Inspect** | Media Properties | View detailed codec, resolution, frame rate, bitrate, and stream information |
| **Convert** | Video Formats | Convert to MP4, MKV, MOV, AVI, WebM with quality presets (CRF 18/23/28) |
| | Audio Formats | Convert to MP3 (128k-320k bitrate), FLAC, WAV |
| | GIF Creation | Convert video clips to animated GIFs with optimized palette |
| | Image Formats | Convert between JPG, PNG, WebP, BMP, TIFF with quality control |
| **Subtitles** | AI Transcription | Generate subtitles using Whisper AI (7 model sizes available) |
| | Sidecar Export | Save as `.srt`, `.vtt`, `.txt`, or `.lrc` files |
| | Soft Subtitles | Embed toggleable subtitle track into video |
| | Hard Subtitles | Burn permanent subtitles directly into video |
| | Multi-language | Support for 99+ languages with auto-detection |
| **Edit** | Trim/Cut | Extract video segments by start/end time (lossless, no re-encoding) |
| | Visual Crop | Interactive GUI to select crop area on video/image |
| | Join/Concatenate | Merge multiple videos with automatic resolution matching |
| **Audio** | Extract Audio | Rip audio track to MP3, FLAC, or WAV |
| | Remove Audio | Create silent version of video (keeps video intact) |
| **Image** | Resize | Scale images with aspect ratio preservation |
| | Rotate | Rotate 90°, 180°, or 270° |
| | Flip | Flip horizontally or vertically |
| | Crop | Visual cropping with click-and-drag selection |
| **Batch** | Batch Convert | Convert all media files in directory at once |

## Detailed Feature Breakdown

### Video Operations

| Operation | Input | Output | Method | Re-encoding |
|-----------|-------|--------|--------|-------------|
| **Convert** | Any video | MP4, MKV, MOV, AVI, WebM | FFmpeg transcode | Yes (CRF quality) |
| **Trim** | Any video | Same format | Stream copy | No (lossless) |
| **Crop** | Any video | Same format | Visual selection + crop filter | Yes |
| **Join** | Multiple videos | Single MP4 | Concat filter + normalize | Yes |
| **To GIF** | Any video | Animated GIF | 2-pass palette optimization | Yes |

### Audio Operations

| Operation | Input | Output | Notes |
|-----------|-------|--------|-------|
| **Extract** | Video with audio | MP3, FLAC, WAV | Preserves original quality for FLAC/WAV |
| **Remove** | Video with audio | Silent video | Stream copy (fast, no re-encoding) |
| **Convert** | Audio file | MP3, FLAC, WAV | Bitrate selection for MP3 |

### Subtitle Generation

| Model | Size | Speed | Accuracy | Languages |
|-------|------|-------|----------|-----------|
| `tiny.en` | ~75 MB | Fastest | Good | English only |
| `base.en` | ~150 MB | Fast | Better | English only |
| `small.en` | ~500 MB | Balanced | Great | English only |
| `medium.en` | ~1.5 GB | Slower | Excellent | English only |
| `small` | ~500 MB | Balanced | Great | 99+ languages |
| `medium` | ~1.5 GB | Slower | Excellent | 99+ languages |
| `large-v3` | ~3 GB | Slowest | Best | 99+ languages |

**Output Options:**
| Type | File Extension | Description |
|------|----------------|-------------|
| Sidecar | `.srt` | SubRip - most compatible format |
| Sidecar | `.vtt` | WebVTT - for web/HTML5 players |
| Sidecar | `.txt` | Plain text transcript |
| Sidecar | `.lrc` | Lyrics format with timestamps |
| Soft Subs | `.mp4/.mkv` | Embedded, toggleable in players |
| Hard Subs | `.mp4/.mkv` | Burned in, always visible |

### Image Operations

| Operation | Options | Notes |
|-----------|---------|-------|
| **Convert** | JPG, PNG, WebP, BMP, TIFF | Quality presets (95%, 80%, 60%) |
| **Resize** | Custom width/height | Use `-1` to preserve aspect ratio |
| **Rotate** | 90° CW, 90° CCW, 180° | Lossless rotation |
| **Flip** | Horizontal, Vertical | Mirror image |
| **Crop** | Visual selection | Interactive GUI with preview |

### Supported Formats

| Type | Supported Formats |
|------|-------------------|
| **Video Input** | `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.gif` |
| **Video Output** | `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`, `.gif` |
| **Audio Input** | `.mp3`, `.flac`, `.wav`, `.ogg`, `.aac`, `.m4a` |
| **Audio Output** | `.mp3`, `.flac`, `.wav` |
| **Image Input** | `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff` |
| **Image Output** | `.jpg`, `.png`, `.webp`, `.bmp`, `.tiff` |
| **Subtitle Output** | `.srt`, `.vtt`, `.txt`, `.lrc` |

## Usage

### Prerequisite: Install FFmpeg

> [!NOTE]
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
If you want to run the tool directly from the source code:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/hariharen9/ffmpeg-this.git
    cd ffmpeg-this
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the tool:**
    ```bash
    python -m src.peg_this.peg_this
    ```

## Subtitle Generation

The subtitle feature uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), a fast and accurate speech-to-text engine powered by OpenAI's Whisper model.

### How it works

1. Select a video file
2. Choose "Generate Subtitles (Whisper)"
3. Pick a model size (tiny to large-v3)
4. Select processing mode (Fast or Accurate)
5. Choose output type:
   - **Sidecar file**: Export as `.srt`, `.vtt`, `.txt`, or `.lrc`
   - **Soft subtitles**: Embed into video (can be toggled on/off in players)
   - **Hard subtitles**: Burn into video (permanent, always visible)

### Supported Languages

Using multilingual models (`small`, `medium`, `large-v3`), you can transcribe audio in 99+ languages including English, Spanish, French, German, Chinese, Japanese, Korean, Hindi, Arabic, and many more.

## Star History

<p align="center">
  <a href="https://star-history.com/#hariharen9/ffmpeg-this&Date">
    <img src="https://api.star-history.com/svg?repos=hariharen9/ffmpeg-this&type=Date" alt="Star History Chart">
  </a>
</p>

## Sponsor

<p align="center">
    <a href="https://github.com/sponsors/hariharen9">
        <img src="https://img.shields.io/github/sponsors/hariharen9?style=for-the-badge&logo=github&color=white" alt="GitHub Sponsors">
    </a>
    <a href="https://www.buymeacoffee.com/hariharen">
        <img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee">
    </a>
</p>

## Contributors

<a href="https://github.com/hariharen9/ffmpeg-this/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=hariharen9/ffmpeg-this" />
</a>

## Contributing

Contributions are welcome! Please see the [Contributing Guidelines](CONTRIBUTING.md) for more information.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

<p align="center">
    Made with ❤️ by <a href="https://hariharen.site">Hariharen</a>
</p>
