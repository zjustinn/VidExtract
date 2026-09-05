"""
downloader.py
─────────────
Core download logic. All yt-dlp calls live here so the UI never
touches subprocess directly. Import this module from anywhere.
"""

import os
import json
import subprocess
import urllib.request
from pathlib import Path

# ── Paths (users edit only these two lines) ───────────────────────────────────
NODE_PATH  = r"C:\Program Files\nodejs\node.exe"
FFMPEG_DIR = r"D:\YouTube Download"

# ── Base yt-dlp flags used in every call ─────────────────────────────────────
YTDLP_BASE = [
    "yt-dlp",
    "--js-runtimes",      f"node:{NODE_PATH}",
    "--remote-components","ejs:github",
    "--ffmpeg-location",  FFMPEG_DIR,
]

# ── All quality tiers (height in pixels) ─────────────────────────────────────
ALL_TIERS = [4320, 2160, 1440, 1080, 720, 480, 360, 240, 144]
TIER_LABELS = {
    4320: "8K",
    2160: "4K Ultra HD",
    1440: "2K / 1440p",
    1080: "1080p Full HD",
     720: "720p HD",
     480: "480p",
     360: "360p",
     240: "240p",
     144: "144p",
}


def build_format(height: int) -> str:
    """Return yt-dlp format string that prefers H.264 at the given height."""
    return (
        f"bestvideo[height<={height}][vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[height<={height}]+bestaudio/best"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Metadata helpers
# ─────────────────────────────────────────────────────────────────────────────

def fetch_info(url: str) -> dict | None:
    """
    Return a dict with video metadata + available quality list.
    Returns None on failure.
    """
    cmd = YTDLP_BASE + ["--dump-json", "--no-download", "--quiet", "--no-warnings", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        raw = json.loads(result.stdout)
    except Exception:
        return None

    # Collect unique heights that have a real video stream
    heights = set()
    for fmt in raw.get("formats", []):
        h = fmt.get("height")
        if h and fmt.get("vcodec", "none") != "none":
            heights.add(h)

    # Build quality list — only tiers that the video actually has
    qualities = []
    for tier in ALL_TIERS:
        if any(h >= tier for h in heights):
            qualities.append({"height": tier, "label": TIER_LABELS[tier]})

    duration = raw.get("duration", 0) or 0
    mins, secs = divmod(int(duration), 60)

    return {
        "title":      raw.get("title", "Unknown"),
        "uploader":   raw.get("uploader", "Unknown"),
        "duration":   duration,
        "duration_str": f"{mins}:{secs:02d}",
        "view_count": raw.get("view_count", 0),
        "thumbnail":  raw.get("thumbnail", ""),
        "qualities":  qualities,          # list of {height, label}
        "url":        url,
    }


def download_thumbnail(url: str, dest: str) -> bool:
    """Download thumbnail image to dest path. Returns True on success."""
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Download helpers
# ─────────────────────────────────────────────────────────────────────────────

def download_full(
    url: str,
    output_dir: str,
    height: int,
    audio_only: bool = False,
    subtitle: bool = False,
    progress_callback=None,
) -> bool:
    """
    Download a full video.
    progress_callback(percent: float, speed: str, eta: str) is called each
    progress update if provided.
    Returns True on success.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_tmpl = os.path.join(output_dir, "%(title)s.%(ext)s")

    if audio_only:
        cmd = YTDLP_BASE + [
            "-f", "bestaudio/best",
            "--extract-audio", "--audio-format", "mp3", "--audio-quality", "192K",
            "-o", out_tmpl, url,
        ]
    else:
        cmd = YTDLP_BASE + [
            "-f", build_format(height),
            "--merge-output-format", "mp4",
            "-o", out_tmpl, url,
        ]

    if subtitle:
        cmd += ["--write-subs", "--write-auto-subs", "--sub-langs", "en"]

    return _run_with_progress(cmd, progress_callback)


def download_clip(
    url: str,
    output_dir: str,
    height: int,
    start: float,
    end: float,
    progress_callback=None,
) -> bool:
    """
    Download only the clip between start and end (in seconds).
    Uses ffmpeg's --download-sections for accurate trimming.
    Returns True on success.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_tmpl = os.path.join(output_dir, "%(title)s_clip_%(section_start)s-%(section_end)s.%(ext)s")

    start_str = _fmt_time(start)
    end_str   = _fmt_time(end)

    cmd = YTDLP_BASE + [
        "-f", build_format(height),
        "--merge-output-format", "mp4",
        "--download-sections", f"*{start_str}-{end_str}",
        "--force-keyframes-at-cuts",
        "-o", out_tmpl,
        url,
    ]

    return _run_with_progress(cmd, progress_callback)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    """Convert float seconds → HH:MM:SS string for yt-dlp."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _run_with_progress(cmd: list, progress_callback=None) -> bool:
    """
    Run a yt-dlp command.
    If progress_callback is given, parse progress lines and call it.
    Returns True on success.
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in process.stdout:
        line = line.rstrip()
        # Print to terminal as well (useful for debugging)
        print(line)

        if progress_callback and "[download]" in line:
            # Example: "[download]  45.3% of   63.02MiB at   4.20MiB/s ETA 00:10"
            parts = line.split()
            try:
                pct_str = next(p for p in parts if p.endswith("%"))
                pct = float(pct_str.replace("%", ""))
                speed = parts[parts.index("at") + 1] if "at" in parts else "?"
                eta   = parts[parts.index("ETA") + 1] if "ETA" in parts else "?"
                progress_callback(pct, speed, eta)
            except Exception:
                pass

    process.wait()
    return process.returncode == 0

#This code was fine but didn't work when there is # or emojis in video, stuck on converting to H.264 codec

# """
# downloader.py
# ─────────────
# Core download logic. All yt-dlp calls live here so the UI never
# touches subprocess directly. Import this module from anywhere.
# """

# import os
# import sys
# import json
# import subprocess
# import urllib.request
# from pathlib import Path

# # ── Paths (users edit only these two lines) ───────────────────────────────────
# NODE_PATH  = r"C:\Program Files\nodejs\node.exe"
# FFMPEG_DIR = r"D:\YouTube Download"

# def get_ytdlp_exe() -> str:
#     """Find yt-dlp.exe — works in VS Code and packaged .exe"""
#     if getattr(sys, 'frozen', False):
#         # Running as packaged .exe
#         return os.path.join(os.path.dirname(sys.executable), "yt-dlp.exe")
#     else:
#         # Running in VS Code — same folder as project root
#         return os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt-dlp.exe")

# def _get_browser() -> str:
#     try:
#         path = os.path.join(os.path.expanduser("~"), ".ytdl_settings.json")
#         with open(path, "r") as f:
#             return json.load(f).get("browser", "firefox")
#     except Exception:
#         return "firefox"

# # ── Base yt-dlp flags used in every call ─────────────────────────────────────
# YTDLP_BASE = [
#     get_ytdlp_exe(),
#     "--js-runtimes",      f"node:{NODE_PATH}",
#     "--remote-components","ejs:github",
#     "--ffmpeg-location",  FFMPEG_DIR,
#     "--progress",
#     "--newline",
#     "--cookies-from-browser", _get_browser(),
# ]

# # ── All quality tiers (height in pixels) ─────────────────────────────────────
# ALL_TIERS = [4320, 2160, 1440, 1080, 720, 480, 360, 240, 144]
# TIER_LABELS = {
#     4320: "8K",
#     2160: "4K Ultra HD",
#     1440: "2K / 1440p",
#     1080: "1080p Full HD",
#      720: "720p HD",
#      480: "480p",
#      360: "360p",
#      240: "240p",
#      144: "144p",
# }


# def build_format(height: int) -> str:
#     """
#     Return yt-dlp format string for the given height.
#     Up to 1080p — prefer H.264 natively.
#     Above 1080p — download best available, FFmpeg converts to H.264 after.
#     """
#     if height <= 1080:
#         return (
#             f"bestvideo[height<={height}][vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]"
#             f"/bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
#             f"/bestvideo[height<={height}]+bestaudio/best"
#         )
#     else:
#         return (
#             f"bestvideo[height<={height}]+bestaudio[ext=m4a]"
#             f"/bestvideo[height<={height}]+bestaudio/best"
#         )


# def convert_to_h264(input_path: str, progress_callback=None) -> bool:
#     """
#     Convert a video file to H.264 using FFmpeg.
#     Replaces the original file with the converted version.
#     Tries GPU (NVIDIA) first, falls back to CPU.
#     """
#     base, ext = os.path.splitext(input_path)
#     temp_path = base + "_h264_temp.mp4"
#     ffmpeg_exe = os.path.join(FFMPEG_DIR, "ffmpeg.exe")

#     if progress_callback:
#         progress_callback(0, "Converting to H.264...", "please wait")

#     for encoder in ["h264_nvenc", "libx264"]:
#         cmd = [
#             ffmpeg_exe,
#             "-i", input_path,
#             "-c:v", encoder,
#             "-preset", "fast",
#             "-crf", "18",
#             "-c:a", "aac",
#             "-b:a", "192k",
#             "-y",
#             temp_path,
#         ]
#         result = subprocess.run(cmd, capture_output=True, text=True)
#         if result.returncode == 0:
#             os.replace(temp_path, input_path)
#             if progress_callback:
#                 progress_callback(100, "Done", "0s")
#             return True

#     if os.path.exists(temp_path):
#         os.remove(temp_path)
#     return False


# # ─────────────────────────────────────────────────────────────────────────────
# # Metadata helpers
# # ─────────────────────────────────────────────────────────────────────────────

# def fetch_info(url: str) -> dict | None:
#     """
#     Return a dict with video metadata + available quality list.
#     Returns None on failure.
#     """
#     cmd = YTDLP_BASE + ["--dump-json", "--no-download", "--quiet", "--no-warnings", url]
#     result = subprocess.run(cmd, capture_output=True, text=True)
#     if result.returncode != 0:
#         return None
#     try:
#         raw = json.loads(result.stdout)
#     except Exception:
#         return None

#     heights = set()
#     for fmt in raw.get("formats", []):
#         h = fmt.get("height")
#         if h and fmt.get("vcodec", "none") != "none":
#             heights.add(h)

#     qualities = []
#     for tier in ALL_TIERS:
#         if any(h >= tier for h in heights):
#             qualities.append({"height": tier, "label": TIER_LABELS[tier]})

#     duration = raw.get("duration", 0) or 0
#     mins, secs = divmod(int(duration), 60)

#     return {
#         "title":        raw.get("title", "Unknown"),
#         "uploader":     raw.get("uploader", "Unknown"),
#         "duration":     duration,
#         "duration_str": f"{mins}:{secs:02d}",
#         "view_count":   raw.get("view_count", 0),
#         "thumbnail":    raw.get("thumbnail", ""),
#         "qualities":    qualities,
#         "url":          url,
#     }


# def download_thumbnail(url: str, dest: str) -> bool:
#     """Download thumbnail image to dest path. Returns True on success."""
#     try:
#         urllib.request.urlretrieve(url, dest)
#         return True
#     except Exception:
#         return False


# # ─────────────────────────────────────────────────────────────────────────────
# # Download helpers
# # ─────────────────────────────────────────────────────────────────────────────

# def download_full(
#     url: str,
#     output_dir: str,
#     height: int,
#     audio_only: bool = False,
#     subtitle: bool = False,
#     progress_callback=None,
# ) -> bool:
#     """
#     Download a full video.
#     For resolutions above 1080p, converts to H.264 after download.
#     """
#     os.makedirs(output_dir, exist_ok=True)
#     out_tmpl = os.path.join(output_dir, "%(title)s.%(ext)s")

#     if audio_only:
#         cmd = YTDLP_BASE + [
#             "-f", "bestaudio/best",
#             "--extract-audio", "--audio-format", "mp3", "--audio-quality", "192K",
#             "-o", out_tmpl, url,
#         ]
#     else:
#         cmd = YTDLP_BASE + [
#             "-f", build_format(height),
#             "--merge-output-format", "mp4",
#             "--print", "after_move:filepath",
#             "-o", out_tmpl, url,
#         ]

#     if subtitle:
#         cmd += ["--write-subs", "--write-auto-subs", "--sub-langs", "en"]

#     ok, filepath = _run_with_progress_and_path(cmd, progress_callback)

#     if ok and not audio_only and height > 1080 and filepath:
#         if progress_callback:
#             progress_callback(0, "Converting to H.264...", "please wait")
#         ok = convert_to_h264(filepath, progress_callback)

#     return ok


# def download_clip(
#     url: str,
#     output_dir: str,
#     height: int,
#     start: float,
#     end: float,
#     progress_callback=None,
# ) -> bool:
#     """
#     Download only the clip between start and end (in seconds).
#     For resolutions above 1080p, converts to H.264 after download.
#     """
#     os.makedirs(output_dir, exist_ok=True)
#     out_tmpl = os.path.join(output_dir, "%(title)s_clip_%(section_start)s-%(section_end)s.%(ext)s")

#     cmd = YTDLP_BASE + [
#         "-f", build_format(height),
#         "--merge-output-format", "mp4",
#         "--download-sections", f"*{_fmt_time(start)}-{_fmt_time(end)}",
#         "--force-keyframes-at-cuts",
#         "--print", "after_move:filepath",
#         "-o", out_tmpl,
#         url,
#     ]

#     ok, filepath = _run_with_progress_and_path(cmd, progress_callback)

#     if ok and height > 1080 and filepath:
#         if progress_callback:
#             progress_callback(0, "Converting to H.264...", "please wait")
#         ok = convert_to_h264(filepath, progress_callback)

#     return ok


# # ─────────────────────────────────────────────────────────────────────────────
# # Internal helpers
# # ─────────────────────────────────────────────────────────────────────────────

# def _fmt_time(seconds: float) -> str:
#     """Convert float seconds → HH:MM:SS string for yt-dlp."""
#     h = int(seconds // 3600)
#     m = int((seconds % 3600) // 60)
#     s = int(seconds % 60)
#     return f"{h:02d}:{m:02d}:{s:02d}"


# def _run_with_progress_and_path(cmd: list, progress_callback=None) -> tuple[bool, str]:
#     """
#     Run a yt-dlp command, stream output live, capture final filepath.
#     Returns (success, filepath).
#     """
#     process = subprocess.Popen(
#         cmd,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.STDOUT,
#         text=True,
#         bufsize=1,
#     )

#     filepath = ""
#     for line in process.stdout:
#         line = line.rstrip()
#         print(line)

#         # Send every line to the UI log box
#         if progress_callback and line:
#             try:
#                 progress_callback(-1, line, "")
#             except Exception:
#                 pass

#         # yt-dlp prints the filepath when --print after_move:filepath is used
#         # it's a plain line with no brackets
#         if line and not line.startswith("[") and not line.startswith("WARNING") and os.sep in line:
#             filepath = line.strip()

#         if progress_callback and "[download]" in line:
#             parts = line.split()
#             try:
#                 pct_str = next(p for p in parts if p.endswith("%"))
#                 pct = float(pct_str.replace("%", ""))

#                 # Extract downloaded size e.g. "23.45MiB"
#                 size = ""
#                 of_idx = next((i for i, p in enumerate(parts) if p == "of"), -1)
#                 if of_idx > 0:
#                     size = parts[of_idx - 1]   # e.g. "23.45MiB"
#                     total = parts[of_idx + 1]  # e.g. "210.00MiB"
#                     size_str = f"{size} / {total}"
#                 else:
#                     size_str = size

#                 speed = parts[parts.index("at") + 1] if "at" in parts else ""
#                 eta   = parts[parts.index("ETA") + 1] if "ETA" in parts else ""

#                 # Pass size info via speed label slot
#                 display_speed = f"{size_str}  ·  {speed}" if size_str else speed
#                 progress_callback(pct, display_speed, eta)
#             except Exception:
#                 pass

#     process.wait()
#     return process.returncode == 0, filepath