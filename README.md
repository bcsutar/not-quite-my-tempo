<div align="center">

# Not Quite My Tempo

### A webcam gesture for stopping AI when it starts playing out of time.

Raise the fist. Hold it by your face. Cut sideways.

The AI stops. The menu bar complains. The bandleader is satisfied.

![macOS](https://img.shields.io/badge/macOS-menu%20bar-111827?logo=apple&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Computer vision](https://img.shields.io/badge/MediaPipe-real--time%20vision-0F766E)
![License: MIT](https://img.shields.io/badge/license-MIT-334155)

</div>

> Inspired by the “not quite my tempo” energy of *Whiplash*.
> This is a joke project with a real gesture detector underneath it.

## What it does

Not Quite My Tempo watches your webcam and recognizes a small two-stage gesture:

1. Put a loose fist next to your face.
2. Snap it outward like you are cutting off a band.

When the gesture fires, the app interrupts the selected target. In the default
demo mode, that target is a deliberately overconfident fake AI that streams
rambling text until you physically tell it to stop.

The same detector can also send `Esc` to a focused ChatGPT, Claude, or browser
window, send `Ctrl+C` to a focused terminal, or deliver a real `SIGINT` to a
subprocess that the app launched itself.

## The joke has engineering underneath

- **No API keys** - the bundled fake AI makes the complete demo reproducible.
- **Real-time computer vision** - MediaPipe Hands and Face Detection run locally.
- **Heuristic gesture recognition** - no custom model training or cloud service.
- **Debounced triggering** - a fist must be held by the face, move outward fast
  enough, sustain briefly, and clear a cooldown before it fires.
- **Swappable controllers** - the gesture detector does not need to know how the
  target is interrupted.
- **Safe focused-app behavior** - app mode sends `Esc` only when the configured
  app is actually frontmost.
- **macOS distribution** - build a drag-to-Applications `.dmg` or run as a
  background menu bar app at login.

## Quick start

The supported development runtime is Python 3.12. MediaPipe `0.10.14` is pinned
because this project uses the classic `mp.solutions` API.

```bash
git clone https://github.com/bcsutar/not-quite-my-tempo.git
cd not-quite-my-tempo

python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Run the self-test first. It validates the gesture state machine and the actual
`SIGINT` interrupt path without opening a camera:

```bash
python selftest.py
```

Then start the zero-setup demo:

```bash
python -m tempo.main
```

The fake AI starts streaming nonsense in a terminal. Raise a fist by your face,
cut sideways, and watch it stop. Press `q` in the camera window to quit.

## Choose your target

### Bundled fake AI

This is the best way to show the project to someone else:

```bash
python -m tempo.main
```

### A real interruptible CLI

The app owns the child process and sends it a real `SIGINT`:

```bash
python -m tempo.main --cmd "your-ai-cli --chat"
```

### A focused browser or terminal window

Use synthetic input when the process is outside this app's control:

```bash
python -m tempo.main --target keypress --combo esc
python -m tempo.main --target keypress --combo ctrl-c
```

On macOS, grant Accessibility permission to the terminal or app running this
command. Linux synthetic input is generally reliable under X11 but may be
blocked by Wayland.

## Menu bar mode

Run quietly as `🥁 tempo` in the macOS menu bar. It shows a live status line,
cut count, Pause/Resume, and Quit. When a cut fires, the title flashes
`🚫 NOT MY TEMPO!`.

```bash
python -m tempo.tray --app "ChatGPT"
```

The focused-app controller checks the frontmost macOS application first. If you
are looking at something other than the configured target, it does nothing.
That makes the gesture safe to perform while the app is running in the
background.

## Install at login

The helper creates an isolated environment, installs the project, and registers
a macOS LaunchAgent:

```bash
./scripts/install_launch_agent.sh
```

Remove it with:

```bash
./scripts/uninstall_launch_agent.sh
```

Logs are written to `~/Library/Logs/NotQuiteMyTempo/`. The first launch requests
Camera permission and still needs Accessibility permission under **System
Settings > Privacy & Security**.

## Build the installer

Build an unsigned drag-to-Applications DMG locally:

```bash
./scripts/build_dmg.sh
```

The artifact is written to `dist/Not-Quite-My-Tempo.dmg`.

For a release build, the same script supports Developer ID signing and
notarization:

```bash
export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export NOTARY_PROFILE="not-quite-my-tempo-notary"
./scripts/build_dmg.sh
```

Without signing variables the build is intentionally unsigned, which is useful
for local demos. macOS may show an extra confirmation the first time an
unsigned build is opened.

## How it works

```text
webcam
  -> MediaPipe face + hand landmarks
  -> loose-fist-by-face hold
  -> outward wrist velocity
  -> sustain + cooldown debounce
  -> controller
       -> subprocess: SIGINT
       -> keypress: Esc / Ctrl+C
       -> app: Esc only if the target app is frontmost
```

The core implementation lives in four small modules:

- `tempo/detector.py` - face-relative gesture detection and debounce logic.
- `tempo/controllers.py` - interrupt strategies with one `.stop()` interface.
- `tempo/main.py` - camera loop, HUD, CLI options, and subprocess demo.
- `tempo/tray.py` - background menu bar experience.

The most useful tuning constants are at the top of `tempo/detector.py`:

| Constant | Meaning |
| --- | --- |
| `NEAR_FACE_RADIUS` | How close the wrist must be to the detected face |
| `HOLD_GRACE_S` | How long a valid hold remains armed |
| `CUT_SPEED` | Minimum outward speed in face-widths per second |
| `MIN_SUSTAIN_S` | How long the cut must persist |
| `COOLDOWN_S` | Quiet period between fired gestures |
| `FIST_CURL_MIN` | Number of curled fingers needed for a loose fist |

## Troubleshooting

**`mediapipe` has no `solutions` attribute**

Use Python 3.12 and reinstall the pinned dependency:

```bash
pip install --force-reinstall "mediapipe==0.10.14"
```

**The camera does not open**

Run the sanity check and grant Camera permission to your terminal:

```bash
python check_camera.py
```

**The focused app does not stop**

Grant Accessibility permission to the terminal or packaged app. Also confirm
that the target name matches the macOS application name, for example:

```bash
python -m tempo.tray --app "Claude"
```

## License

MIT. Use responsibly. Cut off the rambling, not the drummer.
