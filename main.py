"""
main.py
───────
Entry point — just run:  python main.py
"""

import sys
import threading
import subprocess
import multiprocessing

# CRITICAL — must be first line in if __name__ block for PyInstaller on Windows
if sys.platform == "win32":
    multiprocessing.freeze_support()

from ui.main_window import MainWindow


def auto_update_ytdlp(callback):
    try:
        import urllib.request
        import json

        with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as r:
            latest = json.loads(r.read())["info"]["version"]

        import yt_dlp
        installed = yt_dlp.version.__version__

        if installed != latest:
            callback(f"🔄 Updating yt-dlp {installed} → {latest}...")
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "yt-dlp", "-q"],
                check=True, **kwargs
            )
            callback(f"✅ yt-dlp updated to {latest}")
        else:
            callback(f"✅ yt-dlp is up to date ({installed})")

    except Exception as e:
        callback(f"⚠️ yt-dlp update check failed: {e}")


if __name__ == "__main__":
    app = MainWindow()

    def on_update(msg):
        app.after(0, app._append_log, msg)

    threading.Thread(
        target=auto_update_ytdlp,
        args=(on_update,),
        daemon=True
    ).start()

    app.mainloop()