"""
ui/main_window.py
─────────────────
Redesigned main window — sidebar nav, purple/dark theme, clean layout.
Pages: Home (download), History, Settings
Full video download only — clip/trim removed for now.
"""

import os
import io
import json
import threading
import datetime
import urllib.request
import tkinter as tk
import customtkinter as ctk
from PIL import Image

from downloader import fetch_info, download_full, download_clip
from ui.trimmer import TrimmerPanel

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── Palette ───────────────────────────────────────────────────────────────────
BG        = "#0f0f0f"   # app background
SURFACE   = "#1a1a1a"   # sidebar, cards
SURFACE2  = "#222222"   # input fields, inner cards
BORDER    = "#2e2e2e"   # subtle borders
PURPLE    = "#7c3aed"   # primary accent
PURPLE_H  = "#6d28d9"   # hover
PURPLE_DIM= "#3b1f6e"   # muted purple bg
TEXT      = "#f0f0f0"   # primary text
SUBTEXT   = "#888888"   # secondary text
SUCCESS   = "#22c55e"
ERROR     = "#ef4444"
WARNING   = "#f59e0b"

HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".ytdl_history.json")


def load_history() -> list:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(entries: list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(entries[-100:], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class Sidebar(ctk.CTkFrame):
    ITEMS = [
        ("⬇", "Download"),
        ("🕘", "History"),
        ("⚙", "Settings"),
    ]

    def __init__(self, parent, on_select, **kwargs):
        super().__init__(parent, fg_color=SURFACE, corner_radius=0,
                         width=72, **kwargs)
        self.pack_propagate(False)
        self.on_select   = on_select
        self._active     = "Download"
        self._btns       = {}
        self._build()

    def _build(self):
        # App logo
        logo = ctk.CTkLabel(
            self, text="🎬",
            font=ctk.CTkFont(size=26),
            text_color=PURPLE,
        )
        logo.pack(pady=(20, 28))

        for icon, name in self.ITEMS:
            btn = ctk.CTkButton(
                self,
                text=f"{icon}\n{name}",
                width=56, height=56,
                corner_radius=12,
                fg_color=PURPLE_DIM if name == self._active else "transparent",
                hover_color=PURPLE_DIM,
                text_color=TEXT if name == self._active else SUBTEXT,
                font=ctk.CTkFont(size=9),
                command=lambda n=name: self._select(n),
            )
            btn.pack(pady=4)
            self._btns[name] = btn

    def _select(self, name: str):
        for n, b in self._btns.items():
            b.configure(
                fg_color=PURPLE_DIM if n == name else "transparent",
                text_color=TEXT if n == name else SUBTEXT,
            )
        self._active = name
        self.on_select(name)

    def set_active(self, name: str):
        self._select(name)


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("VidExtract")
        self.geometry("1000x700")
        self.minsize(860, 600)
        self.configure(fg_color=BG)

        # State
        self.video_info      = None
        self.thumb_image     = None
        self.selected_height = tk.IntVar(value=0)
        self.audio_only_var  = tk.BooleanVar(value=False)
        self.subtitle_var    = tk.BooleanVar(value=False)
        self.output_dir      = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Downloads")
        )
        self.history         = load_history()
        self._downloading    = False
        self._pulse_job      = None
        self._pulse_dir      = 1
        self._pulse_val      = 0.0

        self._build()

    # ─────────────────────────────────────────────────────────────────────────
    # Shell
    # ─────────────────────────────────────────────────────────────────────────

    def _build(self):
        # Sidebar
        self.sidebar = Sidebar(self, on_select=self._switch_page)
        self.sidebar.pack(side="left", fill="y")

        # Thin purple separator line
        sep = ctk.CTkFrame(self, width=1, fg_color=BORDER, corner_radius=0)
        sep.pack(side="left", fill="y")

        # Page container
        self.page_container = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.page_container.pack(side="left", fill="both", expand=True)

        # Build all pages
        self.pages = {}
        self.pages["Download"] = self._build_download_page()
        self.pages["History"]  = self._build_history_page()
        self.pages["Settings"] = self._build_settings_page()

        self._switch_page("Download")

    def _switch_page(self, name: str):
        for p in self.pages.values():
            p.pack_forget()
        self.pages[name].pack(fill="both", expand=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Download page
    # ─────────────────────────────────────────────────────────────────────────

    def _build_download_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color=BG, corner_radius=0)

        # ── Page header ───────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(page, fg_color="transparent")
        hdr.pack(fill="x", padx=28, pady=(28, 0))
        ctk.CTkLabel(hdr, text="Download",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(hdr, text="High quality YouTube Downloads",
                     font=ctk.CTkFont(size=12),
                     text_color=SUBTEXT).pack(side="left", padx=(12, 0), pady=(4, 0))

        # ── URL input ─────────────────────────────────────────────────────────
        url_card = ctk.CTkFrame(page, fg_color=SURFACE, corner_radius=14)
        url_card.pack(fill="x", padx=28, pady=(18, 0))

        url_inner = ctk.CTkFrame(url_card, fg_color="transparent")
        url_inner.pack(fill="x", padx=16, pady=14)

        self.url_entry = ctk.CTkEntry(
            url_inner,
            placeholder_text="Paste a YouTube URL and press Enter or click Analyse...",
            height=42, font=ctk.CTkFont(size=13),
            fg_color=SURFACE2, border_color=BORDER,
            text_color=TEXT, placeholder_text_color=SUBTEXT,
            corner_radius=10,
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.url_entry.bind("<Return>", lambda e: self._fetch_info())

        self.analyse_btn = ctk.CTkButton(
            url_inner, text="Analyse", width=100, height=42,
            fg_color=PURPLE, hover_color=PURPLE_H,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=10,
            command=self._fetch_info,
        )
        self.analyse_btn.pack(side="left")

        # ── Main area: left info + right controls ─────────────────────────────
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=14)
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        # Left — thumbnail + metadata
        left = ctk.CTkFrame(body, fg_color=SURFACE, corner_radius=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_info_panel(left)

        # Right — quality + progress + download
        right = ctk.CTkFrame(body, fg_color=SURFACE, corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._build_controls_panel(right)

        return page

    def _build_info_panel(self, parent):
        # Thumbnail
        self.thumb_lbl = ctk.CTkLabel(
            parent,
            text="🎬\n\nPaste a URL above\nto load video info",
            font=ctk.CTkFont(size=12), text_color=SUBTEXT,
            width=380, height=214,
            fg_color=SURFACE2, corner_radius=10,
        )
        self.thumb_lbl.pack(padx=14, pady=(14, 10))

        # Divider
        ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(fill="x", padx=14)

        # Metadata
        meta = ctk.CTkFrame(parent, fg_color="transparent")
        meta.pack(fill="x", padx=14, pady=10)

        self.title_lbl = ctk.CTkLabel(
            meta, text="No video loaded",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT, wraplength=340, justify="left", anchor="w",
        )
        self.title_lbl.pack(fill="x")

        self.channel_lbl = ctk.CTkLabel(
            meta, text="",
            font=ctk.CTkFont(size=11), text_color=SUBTEXT,
            anchor="w",
        )
        self.channel_lbl.pack(fill="x", pady=(2, 0))

        pills = ctk.CTkFrame(meta, fg_color="transparent")
        pills.pack(fill="x", pady=(6, 0))

        self.dur_pill = self._pill(pills, "⏱  --:--:--")
        self.dur_pill.pack(side="left", padx=(0, 6))

        self.views_pill = self._pill(pills, "")
        self.views_pill.pack(side="left")

    def _pill(self, parent, text):
        f = ctk.CTkFrame(parent, fg_color=SURFACE2, corner_radius=20)
        lbl = ctk.CTkLabel(f, text=text,
                            font=ctk.CTkFont(size=10), text_color=SUBTEXT)
        lbl.pack(padx=10, pady=3)
        f._lbl = lbl
        return f

    def _set_pill(self, pill, text):
        pill._lbl.configure(text=text)

    def _build_controls_panel(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                        scrollbar_button_color=BORDER,
                                        scrollbar_button_hover_color=PURPLE)
        scroll.pack(fill="both", expand=True, padx=2, pady=2)

        # ── Quality ───────────────────────────────────────────────────────────
        self._section_label(scroll, "Quality")
        self.quality_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self.quality_frame.pack(fill="x", padx=12)
        ctk.CTkLabel(
            self.quality_frame,
            text="Analyse a video to see available qualities",
            font=ctk.CTkFont(size=11), text_color=SUBTEXT,
        ).pack(anchor="w", pady=4)

        # ── Options ───────────────────────────────────────────────────────────
        self._section_label(scroll, "Options")
        opts = ctk.CTkFrame(scroll, fg_color="transparent")
        opts.pack(fill="x", padx=12)

        self.audio_chk = ctk.CTkCheckBox(
            opts, text="Audio only  (MP3)",
            variable=self.audio_only_var,
            font=ctk.CTkFont(size=12), text_color=TEXT,
            fg_color=PURPLE, hover_color=PURPLE_H,
            checkmark_color="white",
            command=self._on_audio_toggle,
        )
        self.audio_chk.pack(anchor="w", pady=(0, 6))

        ctk.CTkCheckBox(
            opts, text="Download subtitles  (English)",
            variable=self.subtitle_var,
            font=ctk.CTkFont(size=12), text_color=TEXT,
            fg_color=PURPLE, hover_color=PURPLE_H,
            checkmark_color="white",
        ).pack(anchor="w")

        # ── Save to ───────────────────────────────────────────────────────────
        self._section_label(scroll, "Save to")
        dir_row = ctk.CTkFrame(scroll, fg_color="transparent")
        dir_row.pack(fill="x", padx=12)

        ctk.CTkEntry(
            dir_row, textvariable=self.output_dir,
            font=ctk.CTkFont(size=11), height=34,
            fg_color=SURFACE2, border_color=BORDER, text_color=TEXT,
            corner_radius=8,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            dir_row, text="Browse", width=72, height=34,
            fg_color=SURFACE2, hover_color=BORDER,
            font=ctk.CTkFont(size=11), text_color=TEXT,
            border_width=1, border_color=BORDER,
            corner_radius=8,
            command=self._browse_dir,
        ).pack(side="left")

        # ── Progress ──────────────────────────────────────────────────────────
        self._section_label(scroll, "Progress")

        prog_card = ctk.CTkFrame(scroll, fg_color=SURFACE2, corner_radius=12)
        prog_card.pack(fill="x", padx=12, pady=(0, 4))

        # Stage + percentage row
        stage_row = ctk.CTkFrame(prog_card, fg_color="transparent")
        stage_row.pack(fill="x", padx=12, pady=(10, 4))

        self.stage_lbl = ctk.CTkLabel(
            stage_row, text="Ready",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT,
        )
        self.stage_lbl.pack(side="left")

        self.pct_lbl = ctk.CTkLabel(
            stage_row, text="",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=PURPLE,
        )
        self.pct_lbl.pack(side="right")

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            prog_card,
            fg_color=BORDER, progress_color=PURPLE,
            height=6, corner_radius=3,
        )
        self.progress_bar.pack(fill="x", padx=12, pady=(0, 6))
        self.progress_bar.set(0)

        # Speed + ETA row
        detail_row = ctk.CTkFrame(prog_card, fg_color="transparent")
        detail_row.pack(fill="x", padx=12, pady=(0, 4))

        self.speed_lbl = ctk.CTkLabel(
            detail_row, text="",
            font=ctk.CTkFont(size=10), text_color=SUBTEXT,
        )
        self.speed_lbl.pack(side="left")

        self.eta_lbl = ctk.CTkLabel(
            detail_row, text="",
            font=ctk.CTkFont(size=10), text_color=SUBTEXT,
        )
        self.eta_lbl.pack(side="right")

        # Live log
        self.log_box = ctk.CTkTextbox(
            prog_card, height=80,
            font=ctk.CTkFont(family="Consolas", size=9),
            fg_color=BG, text_color=SUBTEXT,
            wrap="none", state="disabled",
            corner_radius=8,
        )
        self.log_box.pack(fill="x", padx=12, pady=(0, 10))

        # ── Download button ───────────────────────────────────────────────────
        self.dl_btn = ctk.CTkButton(
            scroll, text="⬇   Download", height=46,
            fg_color=PURPLE, hover_color=PURPLE_H,
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=12,
            state="disabled",
            command=self._start_download,
        )
        self.dl_btn.pack(fill="x", padx=12, pady=(8, 14))

    def _section_label(self, parent, text: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(14, 6))
        ctk.CTkLabel(
            row, text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=SUBTEXT,
        ).pack(side="left")
        ctk.CTkFrame(row, height=1, fg_color=BORDER).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=(2, 0)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # History page
    # ─────────────────────────────────────────────────────────────────────────

    def _build_history_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color=BG, corner_radius=0)

        hdr = ctk.CTkFrame(page, fg_color="transparent")
        hdr.pack(fill="x", padx=28, pady=(28, 18))
        ctk.CTkLabel(hdr, text="History",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT).pack(side="left")

        ctk.CTkButton(
            hdr, text="Clear All", width=90, height=32,
            fg_color="transparent", hover_color=SURFACE,
            border_width=1, border_color=BORDER,
            font=ctk.CTkFont(size=11), text_color=SUBTEXT,
            corner_radius=8,
            command=self._clear_history,
        ).pack(side="right")

        self.history_scroll = ctk.CTkScrollableFrame(
            page, fg_color="transparent",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=PURPLE,
        )
        self.history_scroll.pack(fill="both", expand=True, padx=28, pady=(0, 20))

        self._render_history()
        return page

    def _render_history(self):
        for w in self.history_scroll.winfo_children():
            w.destroy()

        if not self.history:
            ctk.CTkLabel(
                self.history_scroll,
                text="No downloads yet",
                font=ctk.CTkFont(size=13), text_color=SUBTEXT,
            ).pack(pady=40)
            return

        for entry in reversed(self.history):
            card = ctk.CTkFrame(self.history_scroll, fg_color=SURFACE, corner_radius=12)
            card.pack(fill="x", pady=(0, 8))

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=10)

            # Status dot
            dot_color = SUCCESS if entry.get("ok") else ERROR
            ctk.CTkLabel(inner, text="●", font=ctk.CTkFont(size=10),
                         text_color=dot_color).pack(side="left", padx=(0, 8))

            info = ctk.CTkFrame(inner, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(info, text=entry.get("title", "Unknown"),
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=TEXT, anchor="w",
                         wraplength=500).pack(anchor="w")

            meta_txt = "  ·  ".join(filter(None, [
                entry.get("quality", ""),
                entry.get("mode", ""),
                entry.get("date", ""),
            ]))
            ctk.CTkLabel(info, text=meta_txt,
                         font=ctk.CTkFont(size=10), text_color=SUBTEXT,
                         anchor="w").pack(anchor="w", pady=(2, 0))

    def _clear_history(self):
        self.history = []
        save_history(self.history)
        self._render_history()

    def _add_history(self, entry: dict):
        self.history.append(entry)
        save_history(self.history)
        self._render_history()

    # ─────────────────────────────────────────────────────────────────────────
    # Settings page
    # ─────────────────────────────────────────────────────────────────────────

    def _build_settings_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color=BG, corner_radius=0)

        ctk.CTkLabel(page, text="Settings",
                    font=ctk.CTkFont(size=22, weight="bold"),
                    text_color=TEXT).pack(anchor="w", padx=28, pady=(28, 18))

        content = ctk.CTkFrame(page, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=28)

        # Browser cookie selector
        browser_card = ctk.CTkFrame(content, fg_color=SURFACE, corner_radius=14)
        browser_card.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(browser_card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        txt = ctk.CTkFrame(inner, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(txt, text="Browser for YouTube cookies",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(txt,
                    text="yt-dlp reads your browser's YouTube login to avoid bot detection.\nMake sure you are logged into YouTube in the selected browser.",
                    font=ctk.CTkFont(size=10), text_color=SUBTEXT,
                    justify="left").pack(anchor="w", pady=(3, 0))

        self.browser_var = tk.StringVar(value=self._load_setting("browser", "firefox"))
        browser_menu = ctk.CTkOptionMenu(
            inner,
            values=["firefox", "chrome", "edge", "brave", "opera", "chromium"],
            variable=self.browser_var,
            width=140, height=34,
            fg_color=SURFACE2, button_color=PURPLE,
            button_hover_color=PURPLE_H,
            dropdown_fg_color=SURFACE,
            dropdown_hover_color=PURPLE_DIM,
            font=ctk.CTkFont(size=12), text_color=TEXT,
            corner_radius=8,
            command=lambda v: (self._save_setting("browser", v), self._update_browser_status()),
        )
        browser_menu.pack(side="right")

        # Browser status
        self.browser_status = ctk.CTkLabel(
            content, text="",
            font=ctk.CTkFont(size=11), text_color=SUBTEXT,
        )
        self.browser_status.pack(anchor="w", padx=4, pady=(0, 10))
        self._update_browser_status()

        # Output folder
        self._settings_row(
            content,
            label="Default output folder",
            description="Where downloaded files are saved",
            widget_builder=lambda p: self._settings_dir_widget(p),
        )

        # About
        about = ctk.CTkFrame(content, fg_color=SURFACE, corner_radius=14)
        about.pack(fill="x", pady=(10, 0))
        inner2 = ctk.CTkFrame(about, fg_color="transparent")
        inner2.pack(fill="x", padx=20, pady=16)
        ctk.CTkLabel(inner2, text="🎬  YT Downloader",
                    font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(inner2,
                    text="Made by H.\nDownload highest quality YouTube video with H.264 support.",
                    font=ctk.CTkFont(size=11), text_color=SUBTEXT,
                    justify="left").pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(inner2, text="yt-dlp  ·  ffmpeg  ·  Python  ·  CustomTkinter",
                    font=ctk.CTkFont(size=10), text_color=BORDER).pack(anchor="w", pady=(8, 0))

        return page


    def _settings_row(self, parent, label, description, widget_builder):
        card = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=14)
        card.pack(fill="x", pady=(0, 10))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=14)

        txt = ctk.CTkFrame(row, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(txt, text=label,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(txt, text=description,
                     font=ctk.CTkFont(size=10), text_color=SUBTEXT,
                     anchor="w").pack(anchor="w")

        widget_builder(row)

    def _settings_dir_widget(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(side="right")
        ctk.CTkEntry(
            f, textvariable=self.output_dir,
            width=240, height=32,
            font=ctk.CTkFont(size=11),
            fg_color=SURFACE2, border_color=BORDER, text_color=TEXT,
            corner_radius=8,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            f, text="Browse", width=70, height=32,
            fg_color=SURFACE2, hover_color=BORDER,
            border_width=1, border_color=BORDER,
            font=ctk.CTkFont(size=11), text_color=TEXT,
            corner_radius=8,
            command=self._browse_dir,
        ).pack(side="left")

    # ─────────────────────────────────────────────────────────────────────────
    # Fetch info
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_info(self):
        url = self.url_entry.get().strip()
        if not url:
            self._set_stage("⚠  Please paste a URL first", WARNING)
            return
        self._set_stage("🔍  Analysing...", SUBTEXT)
        self.analyse_btn.configure(state="disabled", text="Analysing...")
        self.dl_btn.configure(state="disabled")
        self._reset_progress()
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_worker(self, url):
        info = fetch_info(url)
        self.after(0, self._on_info_ready, info)

    def _on_info_ready(self, info):
        self.analyse_btn.configure(state="normal", text="Analyse")
        if not info:
            self._set_stage("❌  Could not fetch video info — check the URL", ERROR)
            return

        self.video_info = info
        self.title_lbl.configure(text=info["title"])
        self.channel_lbl.configure(text=info["uploader"])
        self._set_pill(self.dur_pill, f"⏱  {info['duration_str']}")
        views = info.get("view_count", 0)
        self._set_pill(self.views_pill,
                       f"👁  {views:,}" if isinstance(views, int) and views else "")

        if info.get("thumbnail"):
            threading.Thread(
                target=self._load_thumb, args=(info["thumbnail"],), daemon=True
            ).start()

        self._build_quality_btns(info["qualities"])
        self.dl_btn.configure(state="normal")
        self._set_stage("✅  Ready to download", SUCCESS)

    def _load_thumb(self, url):
        try:
            with urllib.request.urlopen(url) as r:
                data = r.read()
            img   = Image.open(io.BytesIO(data)).resize((380, 214))
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(380, 214))
            self.after(0, lambda: self.thumb_lbl.configure(image=photo, text=""))
            self.thumb_image = photo
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # Quality buttons
    # ─────────────────────────────────────────────────────────────────────────

    def _build_quality_btns(self, qualities):
        for w in self.quality_frame.winfo_children():
            w.destroy()

        if not qualities:
            ctk.CTkLabel(self.quality_frame, text="No qualities found",
                         font=ctk.CTkFont(size=11), text_color=SUBTEXT
                         ).pack(anchor="w")
            return

        self.selected_height.set(qualities[0]["height"])

        grid = ctk.CTkFrame(self.quality_frame, fg_color="transparent")
        grid.pack(fill="x")

        for i, q in enumerate(qualities):
            tag = "  ★" if i == 0 else ""
            ctk.CTkRadioButton(
                grid,
                text=f"{q['label']}{tag}",
                variable=self.selected_height,
                value=q["height"],
                font=ctk.CTkFont(size=12), text_color=TEXT,
                fg_color=PURPLE, hover_color=PURPLE_H,
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=6, pady=3)

    # ─────────────────────────────────────────────────────────────────────────
    # Download
    # ─────────────────────────────────────────────────────────────────────────

    def _start_download(self):
        if not self.video_info or self._downloading:
            return
        self._downloading = True
        self.dl_btn.configure(state="disabled", text="Downloading...")
        self._reset_progress()
        self._clear_log()
        self._start_pulse()
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        info       = self.video_info
        url        = info["url"]
        out_dir    = self.output_dir.get()
        height     = self.selected_height.get()
        audio_only = self.audio_only_var.get()
        subtitle   = self.subtitle_var.get()

        def on_progress(pct, speed, eta):
            if pct == -1:
                self.after(0, self._append_log, speed)
            elif speed == "Converting to H.264...":
                self.after(0, self._stop_pulse)
                self.after(0, self._start_pulse)
                self.after(0, self._set_stage, "🔄  Converting to H.264...", PURPLE)
                self.after(0, self._append_log, "Converting to H.264 — please wait...")
                self.after(0, self._set_pct, "")
                self.after(0, self._set_speed_eta, "", "")
            else:
                self.after(0, self._stop_pulse)
                self.after(0, self._set_stage, "⬇  Downloading...", TEXT)
                self.after(0, self._update_progress, pct, speed, eta)

        self.after(0, self._set_stage, "⬇  Downloading...", TEXT)
        ok = download_full(url, out_dir, height, audio_only, subtitle, on_progress)
        self.after(0, self._on_done, ok, height, audio_only)

    def _on_done(self, ok: bool, height: int, audio_only: bool):
        self._downloading = False
        self._stop_pulse()
        self.dl_btn.configure(state="normal", text="⬇   Download")

        if ok:
            self.progress_bar.set(1)
            self._set_stage("✅  Download complete!", SUCCESS)
            self._set_pct("100%")
            self._set_speed_eta("", "")
            self._append_log("✅ Done!")

            # Save to history
            quality_label = f"{height}p" if not audio_only else "Audio MP3"
            self._add_history({
                "title":   self.video_info["title"],
                "quality": quality_label,
                "mode":    "Audio only" if audio_only else "Video",
                "date":    datetime.datetime.now().strftime("%b %d, %Y  %H:%M"),
                "ok":      True,
            })
        else:
            self._set_stage("❌  Download failed — check log", ERROR)
            self._add_history({
                "title": self.video_info.get("title", "Unknown"),
                "quality": "", "mode": "", "ok": False,
                "date": datetime.datetime.now().strftime("%b %d, %Y  %H:%M"),
            })

    # ─────────────────────────────────────────────────────────────────────────
    # Progress pulse (animated bar when no % available)
    # ─────────────────────────────────────────────────────────────────────────

    def _start_pulse(self):
        self._pulse_val = 0.0
        self._pulse_dir = 1
        self._pulse_tick()

    def _pulse_tick(self):
        if not self._downloading:
            return
        self._pulse_val += 0.018 * self._pulse_dir
        if self._pulse_val >= 1.0:
            self._pulse_val = 1.0
            self._pulse_dir = -1
        elif self._pulse_val <= 0.0:
            self._pulse_val = 0.0
            self._pulse_dir = 1
        self.progress_bar.set(self._pulse_val)
        self._pulse_job = self.after(30, self._pulse_tick)

    def _stop_pulse(self):
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None

    # ─────────────────────────────────────────────────────────────────────────
    # Progress helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _reset_progress(self):
        self._stop_pulse()
        self.progress_bar.set(0)
        self._set_pct("")
        self._set_speed_eta("", "")

    def _set_stage(self, text, color=TEXT):
        self.stage_lbl.configure(text=text, text_color=color)

    def _set_pct(self, text):
        self.pct_lbl.configure(text=text)

    def _set_speed_eta(self, speed, eta):
        self.speed_lbl.configure(text=speed)
        self.eta_lbl.configure(text=f"ETA {eta}" if eta else "")

    def _update_progress(self, pct, speed, eta):
        self._stop_pulse()
        self.progress_bar.set(pct / 100)
        self._set_pct(f"{pct:.1f}%")
        self.speed_lbl.configure(text=speed if speed else "")
        self.eta_lbl.configure(text=f"ETA {eta}" if eta and eta not in ("please wait", "") else "")

    # def _update_progress(self, pct, speed, eta):
    #     self.progress_bar.set(pct / 100)
    #     self._set_pct(f"{pct:.1f}%")
    #     self._set_speed_eta(speed, eta if eta not in ("please wait", "") else "")

    def _append_log(self, line: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ─────────────────────────────────────────────────────────────────────────
    # Misc
    # ─────────────────────────────────────────────────────────────────────────

    def _on_audio_toggle(self):
        state = "disabled" if self.audio_only_var.get() else "normal"
        for w in self.quality_frame.winfo_children():
            for child in w.winfo_children():
                try:
                    child.configure(state=state)
                except Exception:
                    pass

    def _browse_dir(self):
        from tkinter import filedialog
        d = filedialog.askdirectory(initialdir=self.output_dir.get())
        if d:
            self.output_dir.set(d)

    def _load_setting(self, key: str, default):
        try:
            path = os.path.join(os.path.expanduser("~"), ".ytdl_settings.json")
            with open(path, "r") as f:
                return json.load(f).get(key, default)
        except Exception:
            return default

    def _save_setting(self, key: str, value):
        path = os.path.join(os.path.expanduser("~"), ".ytdl_settings.json")
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data[key] = value
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _update_browser_status(self):
        browser = self._load_setting("browser", "firefox")
        import shutil

        # Windows install paths for each browser
        win_paths = {
            "firefox":  [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            ],
            "chrome":   [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ],
            "edge":     [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ],
            "brave":    [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            ],
            "opera":    [
                r"C:\Users\{}\AppData\Local\Programs\Opera\opera.exe".format(os.getenv("USERNAME", "")),
            ],
            "chromium": [
                r"C:\Program Files\Chromium\Application\chrome.exe",
            ],
        }

        # Check shutil first, then known paths
        found = shutil.which(browser) is not None
        if not found:
            for path in win_paths.get(browser, []):
                if os.path.exists(path):
                    found = True
                    break

        if found:
            self.browser_status.configure(
                text=f"✅  {browser.capitalize()} found on this system",
                text_color=SUCCESS
            )
        else:
            self.browser_status.configure(
                text=f"⚠️  {browser.capitalize()} not detected — make sure it's installed",
                text_color=WARNING
            )