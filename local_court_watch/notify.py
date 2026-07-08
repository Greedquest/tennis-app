"""Desktop/mobile notification, auto-detecting whatever backend is on PATH.

Tries, in order: Termux:API (the user's existing Termux/Tasker setup),
notify-send (Linux desktop), osascript (macOS). Falls back to stdout so a
cron log always shows the alert even with no notifier installed.
"""

import logging
import shutil
import subprocess

_TIMEOUT = 10


def _run(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, check=True, timeout=_TIMEOUT, capture_output=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def send_notification(title: str, message: str) -> None:
    """Fire a notification through the first available backend."""
    if shutil.which("termux-notification") and _run(
        ["termux-notification", "--title", title, "--content", message]
    ):
        return
    if shutil.which("notify-send") and _run(["notify-send", title, message]):
        return
    if shutil.which("osascript"):
        script = f'display notification "{message}" with title "{title}"'
        if _run(["osascript", "-e", script]):
            return

    logging.warning("No notification backend available; printing instead.")
    print(f"[COURT WATCH] {title}\n{message}")
