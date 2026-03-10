"""
ui/player.py
────────────
In-app video preview player using ffmpeg to extract frames.
Plays a locally downloaded 360p preview clip inside the app.
User can scrub, play/pause and set IN/OUT trim points while watching.
"""

import os
import io
import json
import subprocess
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

DARK_BG   = "#1a1a2e"
CARD_BG   = "#16213e"
ACCENT    = "#0f3460"
HIGHLIGHT = "#e94560"
TEXT      = "#eaeaea"
SUBTEXT   = "#a0a0b0"
SUCCESS   = "#4caf50"


def _ffmpeg_exe() -> str:
    from downloader import FFMPEG_DIR
    return os.path.join(FFMPEG_DIR, "ffmpeg.exe")


def _ffprobe_exe() -> str:
    from downloader import FFMPEG_DIR
    return os.path.join(FFMPEG_DIR, "ffprobe.exe")


def get_duration(path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run([
            _ffprobe_exe(), "-v", "quiet",
            "-print_format", "json",
            "-show_format", path
        ], capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


def extract_frame(video_path: str, timestamp: float, width: int, height: int) -> Image.Image | None:
    """Extract a single frame from video at given timestamp using ffmpeg."""
    try:
        cmd = [
            _ffmpeg_exe(),
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-vf", f"scale={width}:{height}",
            "pipe:1",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        if result.returncode == 0 and result.stdout:
            return Image.open(io.BytesIO(result.stdout))
    except Exception:
        pass
    return None


def fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class VideoPlayer(ctk.CTkFrame):
    """
    Embedded video player that plays a local preview clip.
    User can scrub timeline and adjust IN/OUT trim points.
    get_range() returns the final (start, end) in seconds
    relative to the ORIGINAL video (not the preview clip).
    """

    FPS      = 12    # lower fps = smoother on slow machines
    FRAME_MS = int(1000 / FPS)
    W        = 460
    H        = 259   # 16:9

    def __init__(self, parent, original_start: float = 0.0, on_range_change=None, **kwargs):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=10, **kwargs)

        # original_start = where in the original video the preview clip starts
        # all times shown to user are offset by this value
        self.original_start  = original_start
        self.on_range_change = on_range_change

        self.video_path   = None
        self.duration     = 0.0       # duration of the preview clip
        self.current_time = 0.0       # current playhead in clip time
        self.is_playing   = False
        self._play_job    = None
        self._frame_cache = {}
        self._drag        = None      # "start" | "end" | "scrub"

        # Trim handles (in clip time, 0 = start of preview clip)
        self._trim_start = 0.0
        self._trim_end   = 0.0

        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Video canvas
        self.canvas = tk.Canvas(
            self, width=self.W, height=self.H,
            bg="#0a0a1a", highlightthickness=0,
        )
        self.canvas.pack(padx=10, pady=(10, 4))
        self._draw_placeholder()

        # Timeline canvas
        self.timeline = tk.Canvas(
            self, height=40, bg=DARK_BG,
            highlightthickness=0, cursor="hand2"
        )
        self.timeline.pack(fill="x", padx=10, pady=(0, 4))
        self.timeline.bind("<Configure>",      self._tl_draw)
        self.timeline.bind("<ButtonPress-1>",  self._tl_press)
        self.timeline.bind("<B1-Motion>",      self._tl_drag)
        self.timeline.bind("<ButtonRelease-1>",self._tl_release)

        # Controls row
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=10, pady=(0, 6))

        # Time label
        self.time_lbl = ctk.CTkLabel(
            ctrl, text="00:00:00",
            font=ctk.CTkFont(family="Consolas", size=11), text_color=SUBTEXT,
        )
        self.time_lbl.pack(side="left")

        # Step back 5s
        ctk.CTkButton(
            ctrl, text="◀ 5s", width=50, height=28,
            fg_color=ACCENT, hover_color=HIGHLIGHT,
            font=ctk.CTkFont(size=11),
            command=lambda: self._step(-5),
        ).pack(side="left", padx=(8, 2))

        # Play/Pause
        self.play_btn = ctk.CTkButton(
            ctrl, text="▶", width=36, height=28,
            fg_color=HIGHLIGHT, hover_color="#c73652",
            font=ctk.CTkFont(size=13),
            command=self._toggle_play,
        )
        self.play_btn.pack(side="left", padx=2)

        # Step forward 5s
        ctk.CTkButton(
            ctrl, text="5s ▶", width=50, height=28,
            fg_color=ACCENT, hover_color=HIGHLIGHT,
            font=ctk.CTkFont(size=11),
            command=lambda: self._step(5),
        ).pack(side="left", padx=2)

        # Set IN point
        ctk.CTkButton(
            ctrl, text="[ IN", width=46, height=28,
            fg_color="#1a472a", hover_color="#2d6a4f",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._set_in,
        ).pack(side="left", padx=(12, 2))

        # Set OUT point
        ctk.CTkButton(
            ctrl, text="OUT ]", width=46, height=28,
            fg_color="#4a1a1a", hover_color="#6a2d2d",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._set_out,
        ).pack(side="left", padx=2)

        # Trim range display
        self.trim_lbl = ctk.CTkLabel(
            ctrl, text="",
            font=ctk.CTkFont(family="Consolas", size=10), text_color=HIGHLIGHT,
        )
        self.trim_lbl.pack(side="left", padx=10)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def load(self, video_path: str, original_start: float = 0.0):
        """Load a downloaded preview clip."""
        self.stop()
        self._frame_cache.clear()
        self.video_path     = video_path
        self.original_start = original_start
        self.duration       = get_duration(video_path)
        self.current_time   = 0.0
        self._trim_start    = 0.0
        self._trim_end      = self.duration
        self._show_frame(0.0)
        self._tl_draw()
        self._update_labels()

    def stop(self):
        self.is_playing = False
        self.play_btn.configure(text="▶")
        if self._play_job:
            self.after_cancel(self._play_job)
            self._play_job = None

    def get_range(self) -> tuple[float, float]:
        """
        Return (start, end) in ORIGINAL video time.
        Adds original_start offset so caller gets the correct timestamps.
        """
        return (
            self.original_start + self._trim_start,
            self.original_start + self._trim_end,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Playback
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle_play(self):
        if not self.video_path:
            return
        self.is_playing = not self.is_playing
        self.play_btn.configure(text="⏸" if self.is_playing else "▶")
        if self.is_playing:
            self._play_loop()

    def _play_loop(self):
        if not self.is_playing:
            return
        self._show_frame(self.current_time)
        self.current_time += 1.0 / self.FPS
        if self.current_time >= self.duration:
            self.current_time = self._trim_start
            self.stop()
            return
        self._play_job = self.after(self.FRAME_MS, self._play_loop)

    def _step(self, secs: float):
        if not self.video_path:
            return
        self.current_time = max(0.0, min(self.duration, self.current_time + secs))
        self._show_frame(self.current_time)

    # ─────────────────────────────────────────────────────────────────────────
    # Frame rendering
    # ─────────────────────────────────────────────────────────────────────────

    def _show_frame(self, ts: float):
        key = round(ts * self.FPS) / self.FPS
        if key not in self._frame_cache:
            img = extract_frame(self.video_path, key, self.W, self.H)
            if img:
                self._frame_cache[key] = ImageTk.PhotoImage(img)
            else:
                return
        photo = self._frame_cache[key]
        self.canvas.delete("all")
        self.canvas.create_image(self.W // 2, self.H // 2, image=photo, anchor="center")
        self._tl_draw()
        self._update_labels()

    def _draw_placeholder(self):
        self.canvas.create_text(
            self.W // 2, self.H // 2,
            text="Preview will appear here\nafter loading",
            fill=SUBTEXT, font=("Arial", 12), anchor="center", justify="center",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Timeline
    # ─────────────────────────────────────────────────────────────────────────

    PAD   = 12
    TY    = 14
    TH    = 6
    HR    = 8

    def _tl_draw(self, event=None):
        c   = self.timeline
        W   = c.winfo_width() or 460
        dur = max(self.duration, 1)
        x0, x1 = self.PAD, W - self.PAD

        c.delete("all")

        # Track background
        c.create_rectangle(x0, self.TY - self.TH//2, x1, self.TY + self.TH//2,
                           fill="#2a2a4a", outline="")

        # Selected range
        sx = x0 + (self._trim_start / dur) * (x1 - x0)
        ex = x0 + (self._trim_end   / dur) * (x1 - x0)
        c.create_rectangle(sx, self.TY - self.TH//2, ex, self.TY + self.TH//2,
                           fill=HIGHLIGHT, outline="")

        # Playhead
        px = x0 + (self.current_time / dur) * (x1 - x0)
        c.create_line(px, 2, px, 30, fill="white", width=2)

        # IN handle (green)
        c.create_oval(sx-self.HR, self.TY-self.HR, sx+self.HR, self.TY+self.HR,
                      fill="#4caf50", outline="white", width=1)
        c.create_text(sx, self.TY + self.HR + 6, text=fmt_time(self.original_start + self._trim_start),
                      fill="#4caf50", font=("Consolas", 7), anchor="n")

        # OUT handle (red)
        c.create_oval(ex-self.HR, self.TY-self.HR, ex+self.HR, self.TY+self.HR,
                      fill=HIGHLIGHT, outline="white", width=1)
        c.create_text(ex, self.TY + self.HR + 6, text=fmt_time(self.original_start + self._trim_end),
                      fill=HIGHLIGHT, font=("Consolas", 7), anchor="n")

    def _x_to_time(self, x: int) -> float:
        W   = self.timeline.winfo_width() or 460
        pct = (x - self.PAD) / max(W - 2 * self.PAD, 1)
        return max(0.0, min(self.duration, pct * self.duration))

    def _tl_press(self, event):
        if not self.video_path:
            return
        W   = self.timeline.winfo_width() or 460
        dur = max(self.duration, 1)
        sx  = self.PAD + (self._trim_start / dur) * (W - 2 * self.PAD)
        ex  = self.PAD + (self._trim_end   / dur) * (W - 2 * self.PAD)
        r   = self.HR + 4

        if abs(event.x - sx) <= r:
            self._drag = "start"
        elif abs(event.x - ex) <= r:
            self._drag = "end"
        else:
            self._drag = "scrub"
            self.current_time = self._x_to_time(event.x)
            self._show_frame(self.current_time)

    def _tl_drag(self, event):
        if not self._drag or not self.video_path:
            return
        t = self._x_to_time(event.x)
        if self._drag == "start":
            self._trim_start = min(t, self._trim_end - 0.5)
        elif self._drag == "end":
            self._trim_end = max(t, self._trim_start + 0.5)
        elif self._drag == "scrub":
            self.current_time = t
            self._show_frame(t)
        self._tl_draw()
        self._update_labels()
        if self._drag in ("start", "end") and self.on_range_change:
            self.on_range_change(*self.get_range())

    def _tl_release(self, event):
        self._drag = None

    # ─────────────────────────────────────────────────────────────────────────
    # IN / OUT buttons
    # ─────────────────────────────────────────────────────────────────────────

    def _set_in(self):
        self._trim_start = min(self.current_time, self._trim_end - 0.5)
        if self.on_range_change:
            self.on_range_change(*self.get_range())
        self._tl_draw()
        self._update_labels()

    def _set_out(self):
        self._trim_end = max(self.current_time, self._trim_start + 0.5)
        if self.on_range_change:
            self.on_range_change(*self.get_range())
        self._tl_draw()
        self._update_labels()

    def _update_labels(self):
        orig_current = self.original_start + self.current_time
        self.time_lbl.configure(text=fmt_time(orig_current))
        clip_dur = self._trim_end - self._trim_start
        self.trim_lbl.configure(
            text=f"[ {fmt_time(self.original_start + self._trim_start)}"
                 f" → {fmt_time(self.original_start + self._trim_end)}"
                 f"  |  {fmt_time(clip_dur)} ]"
        )