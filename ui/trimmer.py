"""
ui/trimmer.py
─────────────
TrimmerPanel — a dual-handle timeline widget that lets the user
drag start / end markers to select a clip range.

The widget draws directly on a tkinter Canvas so it has no extra
dependencies beyond Pillow (already needed for thumbnails).
"""

import tkinter as tk
import customtkinter as ctk

DARK_BG   = "#1a1a2e"
CARD_BG   = "#16213e"
ACCENT    = "#0f3460"
HIGHLIGHT = "#e94560"
TEXT      = "#eaeaea"
SUBTEXT   = "#a0a0b0"
TRACK_CLR = "#2a2a4a"
RANGE_CLR = "#e9456044"   # semi-transparent red fill
HANDLE_CLR = "#e94560"


def _fmt(seconds: float) -> str:
    """Format float seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class TrimmerPanel(ctk.CTkFrame):
    """
    Dual-handle trim slider.

    Usage:
        trimmer = TrimmerPanel(parent, duration=600)
        start, end = trimmer.get_range()   # returns (float, float) in seconds
    """

    TRACK_H   = 10    # height of the track bar in pixels
    HANDLE_R  = 9     # radius of drag handles
    PAD_X     = 18    # horizontal padding inside canvas

    def __init__(self, parent, duration: float = 0, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.duration   = max(duration, 1)
        self._start_pct = 0.0   # 0.0 – 1.0
        self._end_pct   = 1.0
        self._dragging  = None  # "start" | "end" | None

        # ── Labels row ───────────────────────────────────────────────────────
        lbl_row = ctk.CTkFrame(self, fg_color="transparent")
        lbl_row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(lbl_row, text="Clip Range",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT).pack(side="left")

        self.range_lbl = ctk.CTkLabel(lbl_row, text="",
                                      font=ctk.CTkFont(size=11),
                                      text_color=SUBTEXT)
        self.range_lbl.pack(side="right")

        # ── Canvas ───────────────────────────────────────────────────────────
        self.canvas = tk.Canvas(
            self, height=44, bg=DARK_BG,
            highlightthickness=0, cursor="hand2"
        )
        self.canvas.pack(fill="x", pady=(6, 0))
        self.canvas.bind("<Configure>",      self._on_resize)
        self.canvas.bind("<ButtonPress-1>",  self._on_press)
        self.canvas.bind("<B1-Motion>",      self._on_drag)
        self.canvas.bind("<ButtonRelease-1>",self._on_release)

        # ── Time entry boxes ─────────────────────────────────────────────────
        entry_row = ctk.CTkFrame(self, fg_color="transparent")
        entry_row.pack(fill="x", pady=(6, 4))

        ctk.CTkLabel(entry_row, text="Start", font=ctk.CTkFont(size=11),
                     text_color=SUBTEXT).pack(side="left")
        self.start_entry = ctk.CTkEntry(
            entry_row, width=90, height=30,
            font=ctk.CTkFont(size=12), fg_color=ACCENT,
            border_color=ACCENT, text_color=TEXT,
        )
        self.start_entry.pack(side="left", padx=(4, 16))
        self.start_entry.bind("<FocusOut>", self._on_entry_change)
        self.start_entry.bind("<Return>",   self._on_entry_change)

        ctk.CTkLabel(entry_row, text="End", font=ctk.CTkFont(size=11),
                     text_color=SUBTEXT).pack(side="left")
        self.end_entry = ctk.CTkEntry(
            entry_row, width=90, height=30,
            font=ctk.CTkFont(size=12), fg_color=ACCENT,
            border_color=ACCENT, text_color=TEXT,
        )
        self.end_entry.pack(side="left", padx=(4, 0))
        self.end_entry.bind("<FocusOut>", self._on_entry_change)
        self.end_entry.bind("<Return>",   self._on_entry_change)

        self._update_entries()
        self._redraw()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_duration(self, duration: float):
        """Call this after video info is loaded to set the real duration."""
        self.duration   = max(duration, 1)
        self._start_pct = 0.0
        self._end_pct   = 1.0
        self._update_entries()
        self._redraw()

    def get_range(self) -> tuple[float, float]:
        """Return (start_seconds, end_seconds)."""
        return (
            self._start_pct * self.duration,
            self._end_pct   * self.duration,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Drawing
    # ─────────────────────────────────────────────────────────────────────────

    def _redraw(self):
        c      = self.canvas
        W      = c.winfo_width()  or 400
        H      = c.winfo_height() or 44
        pad    = self.PAD_X
        track_y = H // 2
        r       = self.HANDLE_R

        c.delete("all")

        track_x0 = pad
        track_x1 = W - pad

        # Background track
        c.create_rectangle(
            track_x0, track_y - self.TRACK_H // 2,
            track_x1, track_y + self.TRACK_H // 2,
            fill=TRACK_CLR, outline=""
        )

        # Selected range fill
        sx = track_x0 + self._start_pct * (track_x1 - track_x0)
        ex = track_x0 + self._end_pct   * (track_x1 - track_x0)
        c.create_rectangle(
            sx, track_y - self.TRACK_H // 2,
            ex, track_y + self.TRACK_H // 2,
            fill=HIGHLIGHT, outline=""
        )

        # Start handle
        c.create_oval(sx - r, track_y - r, sx + r, track_y + r,
                      fill=HIGHLIGHT, outline="white", width=2, tags="start_handle")

        # End handle
        c.create_oval(ex - r, track_y - r, ex + r, track_y + r,
                      fill=HIGHLIGHT, outline="white", width=2, tags="end_handle")

        # Time labels below handles
        c.create_text(sx, track_y + r + 8, text=_fmt(self._start_pct * self.duration),
                      fill=SUBTEXT, font=("Consolas", 9), anchor="n")
        c.create_text(ex, track_y + r + 8, text=_fmt(self._end_pct * self.duration),
                      fill=SUBTEXT, font=("Consolas", 9), anchor="n")

        # Duration label on right
        self.range_lbl.configure(
            text=f"{_fmt(self._start_pct * self.duration)}  →  "
                 f"{_fmt(self._end_pct * self.duration)}  "
                 f"({_fmt((self._end_pct - self._start_pct) * self.duration)})"
        )

    def _x_to_pct(self, x: int) -> float:
        W   = self.canvas.winfo_width() or 400
        pad = self.PAD_X
        pct = (x - pad) / max(W - 2 * pad, 1)
        return max(0.0, min(1.0, pct))

    # ─────────────────────────────────────────────────────────────────────────
    # Mouse events
    # ─────────────────────────────────────────────────────────────────────────

    def _on_resize(self, event):
        self._redraw()

    def _on_press(self, event):
        W   = self.canvas.winfo_width() or 400
        pad = self.PAD_X
        sx  = pad + self._start_pct * (W - 2 * pad)
        ex  = pad + self._end_pct   * (W - 2 * pad)
        r   = self.HANDLE_R + 4   # slightly larger hit area

        if abs(event.x - sx) <= r:
            self._dragging = "start"
        elif abs(event.x - ex) <= r:
            self._dragging = "end"
        else:
            self._dragging = None

    def _on_drag(self, event):
        if not self._dragging:
            return
        pct = self._x_to_pct(event.x)
        if self._dragging == "start":
            self._start_pct = min(pct, self._end_pct - 0.01)
        else:
            self._end_pct = max(pct, self._start_pct + 0.01)
        self._update_entries()
        self._redraw()

    def _on_release(self, event):
        self._dragging = None

    # ─────────────────────────────────────────────────────────────────────────
    # Entry box sync
    # ─────────────────────────────────────────────────────────────────────────

    def _update_entries(self):
        self.start_entry.delete(0, "end")
        self.start_entry.insert(0, _fmt(self._start_pct * self.duration))
        self.end_entry.delete(0, "end")
        self.end_entry.insert(0, _fmt(self._end_pct * self.duration))

    def _on_entry_change(self, event):
        try:
            s = self._parse_time(self.start_entry.get())
            e = self._parse_time(self.end_entry.get())
            if 0 <= s < e <= self.duration:
                self._start_pct = s / self.duration
                self._end_pct   = e / self.duration
                self._redraw()
        except ValueError:
            pass
        self._update_entries()

    @staticmethod
    def _parse_time(s: str) -> float:
        """Parse HH:MM:SS or MM:SS or plain seconds → float."""
        parts = s.strip().split(":")
        parts = [float(p) for p in parts]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return parts[0]