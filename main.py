"""
main.py
───────
Entry point — just run:  python main.py
Auto-updates yt-dlp on launch in the background.
"""

import subprocess
import threading
import sys
from ui.main_window import MainWindow

if sys.platform == "win32":
    import multiprocessing
    multiprocessing.freeze_support()


def auto_update_ytdlp(callback):
    """Check PyPI and update yt-dlp if outdated."""
    try:
        import urllib.request
        import json

        # Get latest version from PyPI
        with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as r:
            latest = json.loads(r.read())["info"]["version"]

        # Get installed version
        import yt_dlp
        installed = yt_dlp.version.__version__

        if installed != latest:
            callback(f"🔄 Updating yt-dlp {installed} → {latest}...")

            # Windows: CREATE_NO_WINDOW prevents spawning visible console windows
            kwargs = {}
            if sys.platform == "win32":
                import subprocess
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "yt-dlp", "-q"],
                check=True,
                **kwargs
            )
            callback(f"✅ yt-dlp updated to {latest}")
        else:
            callback(f"✅ yt-dlp is up to date ({installed})")

    except Exception as e:
        callback(f"⚠️ yt-dlp update check failed: {e}")


if __name__ == "__main__":
    app = MainWindow()

    # Run update check in background after app launches
    def on_update(msg):
        app.after(0, app._append_log, msg)

    threading.Thread(
        target=auto_update_ytdlp,
        args=(on_update,),
        daemon=True
    ).start()

    app.mainloop()