"""Controllers: the different ways the app can STOP an AI response.

Each controller exposes a single .stop() method so the main loop is agnostic
about how the interruption actually happens. This is the swappable part --
add a new controller and wire it up with --target on the CLI.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys


class SubprocessController:
    """Runs a child process and interrupts it with SIGINT (Ctrl+C).

    This is the deterministic, portfolio-friendly path: we OWN the process,
    so stopping it is a real signal, not a faked keypress. Used to drive the
    bundled demo target, but works for any Ctrl+C-interruptible CLI
    (e.g. an AI chat CLI) launched the same way.
    """

    def __init__(self, cmd: list[str]):
        self.cmd = cmd
        self.proc: subprocess.Popen | None = None

    def start(self):
        # start_new_session so the child gets its own process group;
        # lets us signal the whole group cleanly.
        self.proc = subprocess.Popen(self.cmd, start_new_session=True)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGINT)
            except ProcessLookupError:
                pass

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def restart(self):
        self.stop()
        if self.proc:
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.start()


class KeypressController:
    """Interrupts whatever window is focused by sending a keystroke.

    Use this to stop a browser ChatGPT/Claude tab (Esc / click) or a terminal
    you don't own (Ctrl+C). Requires `pynput`. Note OS permissions:
      * macOS: grant Accessibility to your terminal/Python.
      * Linux: works under X11; Wayland blocks synthetic input in many setups.
    """

    def __init__(self, combo: str = "esc"):
        self.combo = combo
        try:
            from pynput.keyboard import Controller, Key
        except ImportError:
            print("KeypressController needs pynput: pip install pynput",
                  file=sys.stderr)
            raise
        self._Key = Key
        self._kb = Controller()

    def stop(self):
        Key = self._Key
        if self.combo == "esc":
            self._kb.tap(Key.esc)
        elif self.combo == "ctrl-c":
            with self._kb.pressed(Key.ctrl):
                self._kb.tap("c")

    def alive(self) -> bool:
        return True  # external target; we can't know


class AppController:
    """Send Esc to a macOS app ONLY if it's already the focused (frontmost) app.

    No window switching, no popups. On .stop() it checks which app is frontmost;
    if it's the target (e.g. ChatGPT), it taps Esc to stop the streaming
    response. If you're looking at anything else, it does nothing -- so the
    gesture is safe to make anytime while this runs in the background.

    macOS only. Requires `pynput` AND Accessibility permission for the app
    running this (Terminal / iTerm / your IDE): System Settings -> Privacy &
    Security -> Accessibility.
    """

    def __init__(self, app_name: str = "ChatGPT", key: str = "esc"):
        self.app_name = app_name
        self.key = key
        try:
            from pynput.keyboard import Controller, Key
        except ImportError:
            print("AppController needs pynput: pip install pynput",
                  file=sys.stderr)
            raise
        self._Key = Key
        self._kb = Controller()

    def _frontmost_app(self) -> str:
        """Return the name of the currently focused macOS app (or '')."""
        try:
            out = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to '
                 'get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=1.0,
            )
            return out.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    def stop(self):
        if self._frontmost_app() != self.app_name:
            return  # not looking at the target -> do nothing
        Key = self._Key
        if self.key == "esc":
            self._kb.tap(Key.esc)
        elif self.key == "ctrl-c":
            with self._kb.pressed(Key.ctrl):
                self._kb.tap("c")

    def alive(self) -> bool:
        return True  # external target; we can't know
