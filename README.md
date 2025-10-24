# 🎵 StemMixer — Audio Stem Player

**StemMixer** is a desktop application built with Python and `customtkinter` that allows you to load, separate, and mix audio stems in real time.  
It supports adjustable stem volumes, playback controls, and pre-trained AI models for intelligent music separation.

---

## 🚀 Features

- 🎚️ Real-time stem control (vocals, drums, bass, etc.)
- 🧠 Uses pre-trained AI models for audio separation
- 🕹️ Modern UI built with `customtkinter`
- 💾 Configurable via `config.json`
- 🎨 Custom app icon and clean design
- 🧩 One-file executable build with all assets included

---
## 💾 Download

**[Download the latest StemMixer.exe](https://github.com/your-username/your-repo/releases/latest)**

No installation required — just download and run `StemMixer.exe`.
---

## 📁 Project Structure

```StemMixer/
│
├── main.py # Main application
├── config.json # App configuration file
├── pretrained_models/ # AI model files
│ ├── model1.pt
│ ├── model2.pt
│ └── ...
│
├── icon.ico # Converted icon for the .exe
└── README.md # This file
```

---
## 🧩 Resource Path Helper

When bundled with PyInstaller, files like config.json and pretrained_models are stored inside a temporary directory.
Use this helper in your code to correctly load them in both development and production modes:
```
 import os, sys

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path) 
```

Example:
```
config_path = resource_path("config.json")
model_dir = resource_path("pretrained_models")
```
## ⚒️ Credits

- Built with ❤️ using Python, CustomTkinter, and Spleeter
- Audio separation powered by Deezer’s open-source Spleeter AI model
