<h1 align="center">FFm<u><i>PEG</i></u>-this</h1>

<p align="center">
    <a href="https://pypi.org/project/peg-this/">
        <img src="https://img.shields.io/pypi/v/peg_this?color=blue&label=version" alt="Version">
    </a>
    <a href="https://pepy.tech/project/peg-this">
        <img src="https://static.pepy.tech/badge/peg-this" alt="Downloads">
    </a>
    <a href="https://github.com/hariharen9/ffmpeg-this/stargazers">
        <img src="https://img.shields.io/github/stars/hariharen9/ffmpeg-this?color=yellow" alt="Stars">
    </a>
    <a href="https://github.com/hariharen9/ffmpeg-this/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/hariharen9/ffmpeg-this" alt="License">
    </a>
    <a href="https://github.com/hariharen9/ffmpeg-this">
        <img src="https://img.shields.io/badge/platform-win%20%7C%20macos%20%7C%20linux-blueviolet" alt="Platforms">
    </a>
</p>

<p align="center">
    <b>FFmpeg, but you'll actually use it.</b><br>
    <sub>Professional video editing, AI tools, and downloads — all in an interactive CLI menu. No commands to memorize.</sub>
</p>

<p align="center">
    <img src="/assets/peg.gif" width="720">
</p>

---

## Why This Exists

FFmpeg is powerful. FFmpeg is also this:

```bash
# Crop to 9:16 portrait
ffmpeg -i input.mp4 -vf "crop=iw*9/16:ih:(iw-iw*9/16)/2:0" -c:v libx264 -crf 23 -preset medium -c:a aac output.mp4

# Extract audio as MP3
ffmpeg -i input.mp4 -vn -acodec libmp3lame -ab 320k output.mp3

# Compress to 25MB for Discord
ffmpeg -i input.mp4 -c:v libx264 -b:v $(( 25*8192/$(ffprobe -v error -show_entries format=duration \
-of csv=p=0 input.mp4 | cut -d. -f1) ))k -pass 1 -f null /dev/null && ffmpeg -i input.mp4 -c:v \
libx264 -b:v ... -pass 2 output.mp4

# Add subtitles... good luck
```

**peg_this** replaces all of that:

```bash
peg_this
```

Pick from a menu. Follow the prompts. No flags, no syntax, no StackOverflow.

---

## Get Started in 10 Seconds

```bash
pip install peg_this
```

> **Prerequisite:** [FFmpeg](https://ffmpeg.org/download.html) must be installed. `brew install ffmpeg` (macOS) · `choco install ffmpeg` (Windows) · `sudo apt install ffmpeg` (Linux)

<details>
<summary><b>More install options</b></summary>

**Optional extras:**
```bash
pip install peg_this[download]     # yt-dlp download engine
pip install peg_this[demucs]       # AI music stem separation (~1.5GB)
pip install peg_this[upscale]      # AI video upscaling (~1.5GB)
pip install peg_this[all-ai,download]  # Everything
```

**From source:**
```bash
git clone https://github.com/hariharen9/ffmpeg-this.git && cd ffmpeg-this
pip install -r requirements.txt
python -m src.peg_this.peg_this
```

**Pre-built binaries:** [Download for Windows / macOS / Linux →](https://github.com/hariharen9/ffmpeg-this/releases/latest)

</details>

---

## What Can It Do?

<table>
<tr>
<td width="50%" valign="top">

### 🎬 Video

Convert · Compress · Trim · Crop · Split · Join · Rotate · Flip · Speed · Reverse · Stabilize · Color Grade · Denoise · Watermark · PiP · Loop · Fade · GIF · Change FPS · Change Resolution

</td>
<td width="50%" valign="top">

### 🤖 AI

Auto Subtitles (99 languages) · Brainrot Captions · Smart Reframe · Face Blur · Background Removal · Video Upscaling (Real-ESRGAN) · Music Stem Separation · Auto-Dubbing (24 languages)

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📥 Download

YouTube · TikTok · Twitter · 1000+ sites · Playlists · Audio extraction · Subtitle download · Quality picker · SponsorBlock · Progress bar · Post-download processing

</td>
<td width="50%" valign="top">

### 🎵 Audio

Extract · Remove · Merge · Volume · Fade · Normalize · Visualizer · Convert · Stem Separation

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🖼️ Image

Resize · Rotate · Flip · Crop · Colors · Blur · Sharpen · Effects · Border · Text · Compress · Convert · Background Removal

</td>
<td width="50%" valign="top">

### 📦 Other

Batch Convert · Slideshow Creator · Metadata Editor · File Inspector · GUI Mode · Configurable Encoding · Hardware Acceleration

</td>
</tr>
</table>

---

## CLI Quick Commands

```bash
peg_this                              # Interactive menu
peg_this --gui                        # Launch graphical interface (Experimental, beta)
peg_this -d "https://youtu.be/..."    # Download video (pick quality)
peg_this -dy "https://youtu.be/..."   # Download instantly (best MP4, no prompts)
# more to come... This tool is in active development
```

---

## Spotlight Features

### 📥 Download Engine

Download from **YouTube, TikTok, Twitter, and 1000+ sites** — powered by yt-dlp.

| | |
|---|---|
| **Modes** | Single video · Audio only · Playlist · Subtitles · Thumbnail |
| **Quality** | Up to 4K · MP4/MKV/WebM container picker |
| **Info Panel** | Title, channel ✓, views, likes, duration, codecs, file size — before you download |
| **Audio** | MP3 · FLAC · WAV · AAC · Opus · M4A (128k–320k) |
| **Playlist** | All · First N · Range · Specific items · Auto-numbering |
| **Advanced** | SponsorBlock · Speed limit · Time range · Cookies · Proxy · Embed metadata |
| **After Download** | Trim → Compress → Convert → Subtitles — without leaving peg_this |

**One-liner download:**
```bash
peg_this -dy "https://youtube.com/watch?v=dQw4w9WgXcQ"
```

---

### 📐 AI Smart Reframe

Auto-crop **16:9 → 9:16** keeping the subject in frame. Face tracking with smooth cinematic panning.

| Target | Use Case |
|--------|----------|
| **9:16** | TikTok · Reels · YouTube Shorts |
| **1:1** | Instagram Feed · Twitter/X |
| **4:5** | Instagram Portrait |

> **How:** Samples frames → Haar cascade face detection → Temporal smoothing (EMA) → Per-frame crop → Audio merge. No GPU required.

---

### 💬 AI Subtitles & Captions

Generate subtitles using **Faster-Whisper** with 7 model sizes (tiny → large-v3) in **99+ languages**.

| Output | Description |
|--------|-------------|
| `.srt` / `.vtt` / `.txt` / `.lrc` | Sidecar files |
| Soft subs | Embedded, toggleable in players |
| Hard subs | Burned permanently into video |
| Brainrot | TikTok-style word-by-word animated captions |

---

### 🎙️ AI Auto-Dubbing

Translate and re-voice videos into **24+ languages** — transcription, translation, and voice synthesis all run locally.

Spanish · French · German · Italian · Portuguese · Japanese · Chinese · Korean · Russian · Arabic · Hindi · and more

---

### 🚀 AI Video Upscaling

| Mode | Speed | Best For |
|------|-------|----------|
| Quick (FFmpeg) | ⚡ Instant | Basic upscaling |
| Fast AI | 🚀 Fast | General content |
| Quality AI | 🐢 Slow | Final renders |
| Anime AI | 🚀 Fast | Animation |

Supports **NVIDIA CUDA**, **Apple Silicon (MPS)**, and CPU.

---

### 🖥️ Graphical Interface

```bash
peg_this --gui
```

The full feature set in a hardware-accelerated desktop GUI. Same engine, visual workflow.

> **Beta** — requires `dearpygui` (installed automatically).

---

<details>
<summary><h2>📋 Full Feature Reference (100+ operations)</h2></summary>

### Video Operations

| Operation | Method | Re-encode? |
|-----------|--------|------------|
| Convert (MP4, MKV, MOV, AVI, WebM) | FFmpeg transcode | Yes |
| Compress (target size or CRF) | 2-pass encoding | Yes |
| Change Resolution (4K/1080p/720p/480p/custom) | Scale filter | Yes |
| Change FPS (24/30/60/120) | fps / minterpolate | Yes |
| Trim | Stream copy | **No (lossless)** |
| Crop (visual selection) | crop filter | Yes |
| Split (equal parts or by duration) | Stream copy or re-encode | Configurable |
| Join / Concatenate | Concat filter | Yes |
| Speed (0.25x – 4x) | setpts + atempo | Yes |
| Reverse | Reverse filter | Yes |
| Rotate (90°/180°) / Flip | transpose / hflip/vflip | Yes |
| Fade In/Out (black or white) | fade filter | Yes |
| Loop (N times or target duration) | stream_loop | **No** |
| Color Correction | eq filter | Yes |
| Denoise (fast / quality) | hqdn3d / nlmeans | Yes |
| Blur/Pixelate Region (visual) | boxblur / scale | Yes |
| Picture-in-Picture | overlay filter | Yes |
| Stabilize | vidstab (two-pass) | Yes |
| Add Watermark (image or text) | overlay filter | Yes |
| Extract Frames | Frame extraction | N/A |
| Create GIF | 2-pass palette | Yes |
| Smart Reframe (AI) | Haar face tracking + crop | Yes |
| Background Removal (AI) | rembg (U2-Net) | Yes |
| Brainrot Captions (AI) | Whisper + ASS | Yes |
| Auto-Dubbing (AI) | Whisper + Piper TTS | Yes |
| Video Upscaling (AI) | Real-ESRGAN | Yes |

### Audio Operations

| Operation | Notes |
|-----------|-------|
| Extract from video | MP3, FLAC, WAV |
| Remove from video | Stream copy (fast) |
| Merge with video | Replace or mix |
| Adjust Volume | Presets, dB, multiplier |
| Fade In/Out | 6 curve types |
| Normalize | EBU R128, Peak, RMS, Dynamic |
| Visualizer | Spectrum, Waveform, CQT |
| Convert format | MP3, FLAC, WAV |
| Stem Separation (AI) | Vocals, drums, bass, other (Demucs) |

### Image Operations

| Operation | Options |
|-----------|---------|
| Convert | JPG, PNG, WebP, BMP, TIFF |
| Resize | Custom dimensions, preserve aspect ratio |
| Rotate / Flip | 90° CW/CCW, 180°, horizontal, vertical |
| Crop | Visual interactive selection |
| Adjust Colors | Brightness, contrast, saturation, gamma (8 presets) |
| Blur / Sharpen | 4 blur levels, 3 sharpen levels |
| Effects | Grayscale, sepia, invert |
| Add Border | Custom size, 7 colors + hex |
| Add Text | 7 positions, font, color, shadow/outline |
| Compress | Quality 40-90%, auto format conversion |

### Subtitle Models

| Model | Size | Speed | Languages |
|-------|------|-------|-----------|
| `tiny.en` | ~75 MB | Fastest | English |
| `base.en` | ~150 MB | Fast | English |
| `small.en` | ~500 MB | Balanced | English |
| `medium.en` | ~1.5 GB | Slower | English |
| `small` | ~500 MB | Balanced | 99+ |
| `medium` | ~1.5 GB | Slower | 99+ |
| `large-v3` | ~3 GB | Slowest | 99+ |

### Supported Formats

| Type | Formats |
|------|---------|
| Video In | `.mp4` `.mkv` `.avi` `.mov` `.webm` `.flv` `.wmv` `.gif` |
| Video Out | `.mp4` `.mkv` `.mov` `.avi` `.webm` `.gif` |
| Audio In | `.mp3` `.flac` `.wav` `.ogg` `.aac` `.m4a` |
| Audio Out | `.mp3` `.flac` `.wav` |
| Image | `.jpg` `.png` `.webp` `.bmp` `.tiff` |
| Subtitle | `.srt` `.vtt` `.txt` `.lrc` |

</details>

---

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

MIT License. See [LICENSE](LICENSE) for details.

<p align="center">
    Made with ❤️ by <a href="https://hariharen.site">Hariharen</a>
</p>
