"""Not Quite My Tempo -- macOS menu bar app.

Lives in your menu bar as "🥁 tempo". Watches the webcam in the background;
when you do the fist-cut by your face AND ChatGPT is the focused app, it taps
Esc to stop the response and briefly flashes "🚫 NOT MY TEMPO!" in the bar.

Run:
    python -m tempo.tray                 # targets the ChatGPT app
    python -m tempo.tray --app "ChatGPT" # or any focused app name

Click the menu bar item for a live status line, Pause/Resume, and Quit.

Requires: rumps (menu bar), plus the usual opencv/mediapipe/pynput stack.
    pip install rumps
macOS permissions: Camera AND Accessibility for your terminal (or the built
app) under System Settings -> Privacy & Security.
"""

from __future__ import annotations

import argparse
import threading
import time

try:
    import rumps
except ImportError as e:  # pragma: no cover - only meaningful on macOS
    raise SystemExit(
        "The tray app needs `rumps`:  pip install rumps\n"
        "(macOS only.)"
    ) from e

import cv2

from .controllers import AppController
from .detector import CutoffDetector

IDLE_TITLE = "\U0001F941 tempo"          # 🥁 tempo
FLASH_TITLE = "\U0001F6AB NOT MY TEMPO!"  # 🚫 NOT MY TEMPO!
FLASH_SECONDS = 1.2


class TempoTray(rumps.App):
    def __init__(self, app_name: str, camera: int):
        super().__init__(IDLE_TITLE, quit_button=None)
        self.app_name = app_name
        self.camera = camera

        self.controller = AppController(app_name=app_name, key="esc")
        self.detector = CutoffDetector()

        self.paused = False
        self.running = True
        self.cut_count = 0
        self._flash_until = 0.0
        self._status = "starting camera..."

        # menu
        self.status_item = rumps.MenuItem("Status: starting...")
        self.count_item = rumps.MenuItem("Cuts: 0")
        self.pause_item = rumps.MenuItem("Pause", callback=self.toggle_pause)
        self.menu = [
            self.status_item,
            self.count_item,
            None,  # separator
            self.pause_item,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # background camera thread
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

        # a timer on the main thread updates the title/menu (rumps is not
        # thread-safe, so all UI changes happen here)
        self._ui_timer = rumps.Timer(self._tick, 0.15)
        self._ui_timer.start()

    # ---- UI (main thread only) ------------------------------------------
    def _tick(self, _):
        if time.time() < self._flash_until:
            self.title = FLASH_TITLE
        else:
            self.title = IDLE_TITLE if not self.paused else "\U0001F941 (paused)"
        self.status_item.title = f"Status: {self._status}"
        self.count_item.title = f"Cuts: {self.cut_count}"

    def toggle_pause(self, _):
        self.paused = not self.paused
        self.pause_item.title = "Resume" if self.paused else "Pause"

    def quit_app(self, _):
        self.running = False
        time.sleep(0.2)
        rumps.quit_application()

    # ---- camera loop (background thread) --------------------------------
    def _loop(self):
        cap = cv2.VideoCapture(self.camera)
        if not cap.isOpened():
            self._status = f"camera {self.camera} unavailable"
            return
        self._status = "watching"
        try:
            while self.running:
                if self.paused:
                    time.sleep(0.1)
                    continue
                ok, frame = cap.read()
                if not ok:
                    self._status = "camera read failed"
                    break
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                _results, state = self.detector.process(rgb)

                if state.holding:
                    self._status = "fist by face - cut!"
                elif state.face:
                    self._status = "watching"
                else:
                    self._status = "no face in view"

                if state.fired:
                    self.controller.stop()           # Esc, only if app focused
                    self.cut_count += 1
                    self._flash_until = time.time() + FLASH_SECONDS
        finally:
            cap.release()
            self.detector.close()


def main():
    ap = argparse.ArgumentParser(description="Not Quite My Tempo (menu bar)")
    ap.add_argument("--app", default="ChatGPT",
                    help="focused macOS app to interrupt (default: ChatGPT)")
    ap.add_argument("--camera", type=int, default=0)
    args = ap.parse_args()
    TempoTray(args.app, args.camera).run()


if __name__ == "__main__":
    main()
