<h1 align="center">FFm<u><i>PEG</i></u>-this</h1>

<p align="center">
    <a href="https://pypi.org/project/peg-this/">
        <img src="https://img.shields.io/pypi/v/peg_this?color=blue&label=version" alt="PyPI Version">
    </a>
    <a href="https://pepy.tech/project/peg-this">
        <img src="https://static.pepy.tech/badge/peg-this" alt="Downloads">
    </a>
    <a href="https://github.com/hariharen9/ffmpeg-this/stargazers">
        <img src="https://img.shields.io/github/stars/hariharen9/ffmpeg-this?color=yellow" alt="GitHub Stars">
    </a>
    <a href="https://github.com/hariharen9/ffmpeg-this/network/members">
        <img src="https://img.shields.io/github/forks/hariharen9/ffmpeg-this?color=lightgrey" alt="GitHub Forks">
    </a>
    <a href="https://github.com/hariharen9/ffmpeg-this/issues">
        <img src="https://img.shields.io/github/issues/hariharen9/ffmpeg-this?color=red" alt="GitHub Issues">
    </a>
    <a href="https://github.com/hariharen9/ffmpeg-this/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/hariharen9/ffmpeg-this" alt="License">
    </a>
    <br>
    <a href="https://github.com/hariharen9/ffmpeg-this">
        <img src="https://img.shields.io/badge/platform-win%20%7C%20macos%20%7C%20linux-blueviolet" alt="Supported Platforms">
    </a>
    <a href="https://ffmpeg.org/">
        <img src="https://img.shields.io/badge/FFmpeg-Powered-007808?logo=ffmpeg&logoColor=white" alt="FFmpeg">
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
| | Compress Video | Target file size (e.g., 25MB for Discord) or CRF quality presets |
| | Change Resolution | Scale to 4K, 1080p, 720p, 480p, or custom resolution |
| | Change FPS | Convert frame rate (24/30/60/120 fps) with optional smooth interpolation |
| **Subtitles** | AI Transcription | Generate subtitles using Whisper AI (7 model sizes available) |
| | Brainrot Captions | TikTok/Reels style animated word-by-word captions (5 styles) |
| | Sidecar Export | Save as `.srt`, `.vtt`, `.txt`, or `.lrc` files |
| | Soft Subtitles | Embed toggleable subtitle track into video |
| | Hard Subtitles | Burn permanent subtitles directly into video |
| | Multi-language | Support for 99+ languages with auto-detection |
| **Edit** | Trim/Cut | Extract video segments by start/end time (lossless, no re-encoding) |
| | Visual Crop | Interactive GUI to select crop area on video/image |
| | Split Video | Divide video into equal parts or by duration |
| | Join/Concatenate | Merge multiple videos with automatic resolution matching |
| **Audio** | Extract Audio | Rip audio track to MP3, FLAC, or WAV |
| | Separate Music Stems | AI separation of Vocals, Drums, Bass, Other (Demucs) |
| | Remove Audio | Create silent version of video (keeps video intact) |
| | Merge Audio | Replace or mix audio track with video |
| | Adjust Volume | Increase/decrease volume (presets, dB, multiplier) |
| | Audio Fade In/Out | Fade audio at start/end (6 curve types) |
| | Normalize Audio | EBU R128, Peak, RMS, or Dynamic normalization |
| **Effects** | Smooth Slow Motion | Optical Flow (AI) for buttery smooth slow motion |
| | Change Speed | Adjust playback speed (0.25x to 4x) with audio pitch preservation |
| | Reverse Video | Play video backwards (includes audio) |
| | Rotate Video | Rotate 90° clockwise, counter-clockwise, or 180° |
| | Flip Video | Flip horizontally (mirror) or vertically |
| | Video Fade In/Out | Fade to/from black or white at start/end |
| | Loop Video | Repeat video N times or to target duration |
| | Color Correction | Brightness, contrast, saturation with presets |
| | Denoise Video | Reduce grain/noise (hqdn3d fast / nlmeans quality) |
| | Blur/Pixelate Region | Visual selection to blur or pixelate areas |
| | Add Watermark | Overlay image or text with custom positioning |
| | Picture-in-Picture | Overlay smaller video on main video |
| | Video Stabilization | Reduce camera shake (Light/Medium/Heavy) |
| | Extract Frames | Export single frame, every N seconds, or all frames as images |
| **AI** | Background Removal | AI-powered background removal for images and videos (rembg) |
| | Music Separation | Isolate vocals and instruments using Demucs (2/4/6 stems) |
| | Auto Blur Faces | AI face detection and automatic blurring (OpenCV/MediaPipe) |
| | Brainrot Captions | TikTok-style word-by-word animated captions with Whisper |
| | Auto-Dubbing | AI voice translation to 24+ languages with Whisper + Piper TTS |
| | Video Upscaling | AI super-resolution with Real-ESRGAN (2x/4x) + fast FFmpeg upscale |
| **Image** | Transform | Resize, rotate, flip, crop with visual selection |
| | Adjust Colors | Brightness, contrast, saturation, gamma with 8 presets |
| | Blur / Sharpen | Gaussian blur or sharpen with strength control |
| | Effects | Grayscale, sepia, invert (negative) |
| | Add Border | Solid color borders with custom padding |
| | Add Text | Text overlay with position, font, color, shadow/outline options |
| | Compress | Optimize file size with quality control (JPG/PNG/WebP) |
| **Other** | Create Slideshow | Create video from images with background music |
| | Audio Visualizer | Generate stunning audio visualization videos (spectrum, waveform, CQT) |
| | Metadata Editor | View, edit, clear, or copy video metadata |
| | Create GIF (Advanced) | Custom FPS, size, quality, loop options |
| **Batch** | Batch Convert | Convert all media files in directory at once |

<details>
<summary><h2>Detailed Feature Breakdown</h2></summary>

### Video Operations

| Operation | Input | Output | Method | Re-encoding |
|-----------|-------|--------|--------|-------------|
| **Convert** | Any video | MP4, MKV, MOV, AVI, WebM | FFmpeg transcode | Yes (CRF quality) |
| **Compress** | Any video | Same format | 2-pass encoding | Yes (target size/CRF) |
| **Change Resolution** | Any video | Same format | Scale filter | Yes |
| **Change FPS** | Any video | Same format | fps filter / minterpolate | Yes |
| **Trim** | Any video | Same format | Stream copy | No (lossless) |
| **Crop** | Any video | Same format | Visual selection + crop filter | Yes |
| **Split** | Any video | Multiple segments | Stream copy or re-encode | Configurable |
| **Join** | Multiple videos | Single MP4 | Concat filter + normalize | Yes |
| **Change Speed** | Any video | Same format | setpts + atempo filters | Yes |
| **Reverse** | Any video | Same format | Reverse filter | Yes |
| **Rotate** | Any video | Same format | transpose filter | Yes |
| **Flip** | Any video | Same format | hflip/vflip filter | Yes |
| **Video Fade** | Any video | Same format | fade filter | Yes |
| **Loop Video** | Any video | Same format | stream_loop | No (stream copy) |
| **Color Correction** | Any video | Same format | eq filter | Yes |
| **Denoise** | Any video | Same format | hqdn3d/nlmeans filter | Yes |
| **Blur/Pixelate** | Any video | Same format | Visual selection + boxblur/scale | Yes |
| **Auto Blur Faces** | Any video | Same format | MediaPipe AI + frame-by-frame | Yes |
| **Picture-in-Picture** | Two videos | Same format | overlay filter | Yes |
| **Stabilize** | Any video | Same format | vidstab (two-pass) | Yes |
| **Add Watermark** | Any video | Same format | Overlay filter | Yes |
| **Extract Frames** | Any video | PNG/JPG images | Frame extraction | N/A |
| **To GIF** | Any video | Animated GIF | 2-pass palette optimization | Yes |
| **Background Removal** | Image/Video | PNG/WebM/MP4 | rembg AI (U2-Net) | Yes |
| **Brainrot Captions** | Any video | Same format | Whisper + ASS subtitles | Yes |
| **Auto-Dubbing** | Any video | Same format | Whisper + Piper TTS | Yes |
| **Video Upscaling** | Any video | Same format | Real-ESRGAN / FFmpeg scale | Yes |

### Audio Operations

| Operation | Input | Output | Notes |
|-----------|-------|--------|-------|
| **Extract** | Video with audio | MP3, FLAC, WAV | Preserves original quality for FLAC/WAV |
| **Remove** | Video with audio | Silent video | Stream copy (fast, no re-encoding) |
| **Merge** | Video + Audio file | Video with new audio | Replace or mix audio tracks |
| **Adjust Volume** | Video/Audio | Same format | Presets, multiplier, or dB value |
| **Audio Fade** | Video/Audio | Same format | 6 curve types (linear, log, exp, sine) |
| **Normalize** | Video/Audio | Same format | EBU R128, Peak, RMS, Dynamic |
| **Visualizer** | Audio/Video | MP4 video | Spectrum, Waveform, CQT, Vector Scope |
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
| **Adjust Colors** | Brightness, contrast, saturation, gamma | 8 presets + custom mode |
| **Blur / Sharpen** | 4 blur levels, 3 sharpen levels | Gaussian blur, unsharp mask |
| **Effects** | Grayscale, Sepia, Invert | One-click color effects |
| **Add Border** | Custom size, 7 colors + hex | Equal or custom padding |
| **Add Text** | 7 positions, custom font/color | Shadow, outline, background box styles |
| **Compress** | Quality 40-90% | Auto format conversion |

### AI Features

| Feature | Description | Models/Options |
|---------|-------------|----------------|
| **Subtitles** | AI speech-to-text transcription | Whisper tiny to large-v3, 99+ languages |
| **Brainrot Captions** | TikTok-style animated captions | 5 styles, word-by-word sync |
| **Auto-Dubbing** | Translate and re-voice video | 24 languages, multiple voices per language |
| **Music Separation** | Isolate vocals/instruments | Demucs 2/4/6 stems, MP3/FLAC/WAV output |
| **Background Removal** | Remove background from image/video | Transparent, green screen, solid color |
| **Face Blur** | Auto-detect and blur faces | MediaPipe AI or OpenCV Haar |
| **Video Upscaling** | AI super-resolution | Real-ESRGAN 7 models, FFmpeg fast mode |

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

</details>

## Usage

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
This is the easiest way to get started. This will install the core tool with all features.

```bash
pip install peg_this
```

**Optional Heavy AI Features** (not included by default to keep install fast):
```bash
# Music Stem Separation (Demucs) - ~1.5GB, requires PyTorch
pip install peg_this[demucs]

# AI Video Upscaling (Real-ESRGAN) - ~1.5GB, requires PyTorch
pip install peg_this[upscale]

# Install both
pip install peg_this[all-ai]
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

## 🖥️ Graphical User Interface (New!)

**Your Studio in a Shell... now has a Window!**

We've brought the full power of `peg_this` to the desktop. The entire massive feature set—from AI subtitles and background removal to format conversions and brainrot captions—is now available in a fully hardware-accelerated Graphical User Interface.

Enjoy the same robust FFmpeg backend with a modern visual workflow. Whether you're a terminal warrior or a mouse-clicker, we've got you covered. Same powerful engine, two ways to drive.

### Launching the GUI
Run the tool with the `--gui` flag:

```bash
peg_this --gui
```

> **Note:** The GUI is currently in **Beta**. It requires `dearpygui` and `opencv-python` (installed automatically).

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

## AI Auto-Dubbing

Automatically translate and re-voice your videos into 24+ languages using AI.

### How it works

1. Select a video file
2. Choose "AI Auto-Dubbing"
3. Select target language (Spanish, French, German, Japanese, etc.)
4. Choose a voice (multiple male/female options per language)
5. Set original audio volume (mute, quiet, or mix)

### Supported Languages

| Language | Voices Available |
|----------|------------------|
| Spanish (ES/MX) | 3 voices |
| French | 2 voices |
| German | 2 voices |
| Italian | 2 voices |
| Portuguese (BR/PT) | 2 voices |
| Japanese | 2 voices |
| Chinese | 2 voices |
| Korean | 1 voice |
| Russian | 2 voices |
| Arabic | 1 voice |
| Hindi | 1 voice |
| And 13 more... | Various |

> **Note:** Uses Whisper for transcription, deep-translator for translation, and Piper TTS for voice synthesis. All processing runs locally.

## AI Video Upscaling

Enhance video resolution using AI super-resolution or fast FFmpeg scaling.

### Modes

| Mode | Speed | Quality | Use Case |
|------|-------|---------|----------|
| **Quick (FFmpeg)** | ⚡ Fastest | Good | Basic upscaling, large files |
| **Fast AI** | 🚀 Fast | Great | General purpose, balanced |
| **Quality AI** | 🐢 Slow | Best | Final renders, quality priority |
| **Anime AI** | 🚀 Fast | Best for animation | Cartoons, anime content |

### AI Models (Real-ESRGAN)

| Model | Scale | Speed | Best For |
|-------|-------|-------|----------|
| `RealESRGAN_x2plus` | 2x | Fastest | 1080p → 4K |
| `realesr-general-x4v3` | 4x | Fast | General content |
| `RealESRGAN_x4plus` | 4x | Slow | Maximum quality |
| `realesr-animevideov3` | 4x | Fast | Anime/cartoons |

> **Hardware:** Supports NVIDIA CUDA, Apple Silicon (MPS), and CPU. GPU recommended for reasonable speeds.

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
