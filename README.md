# Music Stem Separator (Demucs Edition)

[![GitHub Releases](https://img.shields.io/github/v/release/dat514/music-stem-separator?include_prereleases=&sort=semver&color=brightgreen)](https://github.com/dat514/music-stem-separator/releases)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A user-friendly desktop application for downloading audio from YouTube/SoundCloud and separating it into stems (vocals, drums, bass, etc.) using the powerful Demucs AI model. Built with a modern dark/light theme interface, batch processing, and an integrated stem mixer/player for instant previews.

## ✨ Features

- **Audio Download**: High-quality MP3 downloads (up to 320kbps) from YouTube, SoundCloud, or other supported URLs via yt-dlp.
- **Stem Separation**: AI-powered separation into 2 stems (Vocals + Instrumental) or 4 stems (Vocals, Drums, Bass, Other) using Demucs (HTDemucs or MDX-Extra models).
- **Batch Processing**: Handle multiple URLs at once.
- **Post-Processing**: Automatic audio enhancement (high-pass filter, compression, normalization) for cleaner stems.
- **Integrated Player**: Mix and play stems with individual volume controls, mute toggles, seek bar, and master volume. Supports local file playback too.
- **User-Friendly UI**: CustomTkinter-based interface with theme toggle (dark/light), progress tracking, and easy output folder selection.
- **Cross-Platform**: Works on Windows, macOS, and Linux.

## 🚀 Quick Start

### Download Pre-Built Executable (Recommended)
No installation required! Grab the latest release:

1. Go to [Releases](https://github.com/dat514/music-stem-separator/releases).
2. Download the appropriate EXE file (e.g., `MusicStemSeparator-v1.1.exe` for Windows).
3. Run the EXE directly. Dependencies like FFmpeg and yt-dlp are bundled.

**Note**: On first run, it may prompt for FFmpeg if not detected—download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

### Manual Installation (For Developers)
1. Clone the repo:
   ```
   git clone https://github.com/dat514/music-stem-separator.git
   cd music-stem-separator
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   (Includes: customtkinter, pygame, librosa, soundfile, pydub, torch, torchaudio, demucs, yt-dlp)

3. Ensure FFmpeg is installed and in your PATH (required for audio processing).

4. Run the app:
   ```
   python main.py
   ```

### Usage
1. Paste one or more URLs into the "Source URL(s)" textbox (one per line).
2. Select audio quality (128/192/320kbps) and processing mode (Download Only or Download + Separate).
3. Choose stem count (2 or 4 stems).
4. Set output directory and click **Start Processing**.
5. Once done, use the built-in player to mix and audition stems, or open the folder for WAV files.

**Pro Tip**: For local files, use the "Open Local Audio" button in the player section to load and play without downloading.

## 📁 Output Structure
```
MusicStems/
├── Song Title.mp3          # Downloaded audio (if Download Only mode)
└── Song Title/             # Stem folder
    ├── separated 2 stems/             # For 2-stem mode
    │   ├── vocals.wav
    │   └── instrumental.wav
    └── separated 4 stems/           # For 4-stem mode
        ├── vocals.wav
        ├── drums.wav
        ├── bass.wav
        └── other.wav
```

## 🛠️ Dependencies & Troubleshooting
- **yt-dlp**: For downloads (`pip install yt-dlp`).
- **FFmpeg**: Essential for audio conversion (auto-detected).
- **Demucs**: Handles separation (`pip install demucs[torch]`—GPU recommended for speed).
- **Common Issues**:
  - **Length Error in Separation**: Fixed in v1.1—long tracks are auto-chunked.
  - **CUDA OOM**: Use CPU mode or shorter segments via Demucs params.
  - **No Audio Output**: Check sample rate (forces 44.1kHz) and volume sliders.

For bugs, open an issue on GitHub!

## ⚒️ Credits
Built with ❤️ using Python, CustomTkinter, and Demucs  
Audio separation powered by Facebook's open-source Demucs AI model  

Inspired by similar tools like Spleeter-based apps. Thanks to the open-source community for libraries like Librosa, Pydub, and Pygame.

