# 🎬 YT Downloader — For Editors

A clean, dark-mode desktop application for downloading YouTube videos in the highest quality available. Built by editors, for editors — with clip trimming so you only download exactly what you need.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## ✨ Features

- **Smart quality detection** — analyses each video and shows only available resolutions (144p → 8K)
- **H.264 priority** — downloads in the most compatible codec for editing software
- **Clip trimmer** — drag a visual timeline to download only a specific portion of a video
- **Full video download** — with audio track merged into a single MP4
- **Audio only** — extract MP3 at 192kbps
- **Subtitle download** — optional English subtitles
- **Dark mode UI** — easy on the eyes during long editing sessions

---

## 🚀 Getting Started

### Requirements
- Python 3.10+
- Node.js (LTS) — [nodejs.org](https://nodejs.org)
- FFmpeg — [github.com/BtbN/FFmpeg-Builds/releases](https://github.com/BtbN/FFmpeg-Builds/releases)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/yt-downloader.git
cd yt-downloader

# 2. Create and activate a virtual environment
python -m venv ytenv
ytenv\Scripts\activate.bat       # Windows CMD
# ytenv\Scripts\Activate.ps1    # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt
```

### Configuration

Open `downloader.py` and update these two lines at the top to match your system:

```python
NODE_PATH  = r"C:\Program Files\nodejs\node.exe"   # path to node.exe
FFMPEG_DIR = r"D:\YouTube Download"                 # folder containing ffmpeg.exe
```

To find your Node.js path, run in PowerShell:
```powershell
(Get-Command node -ErrorAction SilentlyContinue).Source
```

### Run

```bash
python main.py
```

---

## 📁 Project Structure

```
yt-downloader/
├── main.py              # Entry point — run this
├── downloader.py        # All yt-dlp logic (no UI code here)
├── ui/
│   ├── main_window.py   # Main application window
│   └── trimmer.py       # Visual clip trimmer widget
├── requirements.txt     # Python dependencies
└── README.md
```

---

## 🤝 Contributing

Pull requests are welcome! Some ideas for contributions:
- [ ] Playlist support (download all videos from a playlist)
- [ ] Download queue / batch downloads
- [ ] Download history log
- [ ] Windows `.exe` packaging with PyInstaller
- [ ] Linux / macOS support

### To contribute:
1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push and open a Pull Request

---

## ⚠️ Disclaimer

This tool is intended for downloading content you have the right to download (e.g. your own videos, Creative Commons licensed footage, or videos for personal offline use). Please respect YouTube's Terms of Service and content creators' rights.

---

## 📄 License

MIT — free to use, modify, and distribute.
