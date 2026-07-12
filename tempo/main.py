"""Not Quite My Tempo -- gesture-controlled AI interrupt.

Raise your hand up next to your face (loose fist), then cut it sideways/away --
the Fletcher move -- and the app stops whatever AI response is streaming.

Run the self-contained demo:
    python -m tempo.main

Drive a real interruptible CLI instead of the bundled fake AI:
    python -m tempo.main --cmd "your-ai-cli --chat"

Interrupt a focused browser tab / external window instead of a subprocess:
    python -m tempo.main --target keypress --combo esc
"""

from __future__ import annotations

import argparse
import sys

import cv2
import mediapipe as mp

from .controllers import AppController, KeypressController, SubprocessController
from .detector import CutoffDetector

mp_draw = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands

GREEN = (80, 220, 80)
RED = (60, 60, 235)
AMBER = (40, 190, 240)
WHITE = (245, 245, 245)


def draw_hud(frame, state, flash_frames):
    h, w = frame.shape[:2]

    # cut-speed meter
    vmax = 2.5
    filled = max(0.0, min(state.velocity / vmax, 1.0))
    x0, y0, bw, bh = 20, h - 40, 220, 18
    cv2.rectangle(frame, (x0, y0), (x0 + bw, y0 + bh), WHITE, 1)
    cv2.rectangle(frame, (x0, y0), (x0 + int(bw * filled), y0 + bh), GREEN, -1)
    cv2.putText(frame, f"cut {state.velocity:4.1f}", (x0, y0 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE, 1, cv2.LINE_AA)

    if flash_frames > 0:
        cv2.rectangle(frame, (0, 0), (w, 70), RED, -1)
        cv2.putText(frame, "NOT QUITE MY TEMPO", (20, 48),
                    cv2.FONT_HERSHEY_DUPLEX, 1.1, WHITE, 2, cv2.LINE_AA)
        return

    if state.holding:
        label, color = "HAND BY FACE - now CUT away!", GREEN
    elif not state.face:
        label, color = "show your face to the camera", WHITE
    elif not state.hand:
        label, color = "raise a fist by your face", WHITE
    else:
        label, color = "bring your fist UP next to your face", AMBER
    cv2.putText(frame, label, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)


def build_controller(args):
    if args.target == "app":
        return AppController(app_name=args.app, key=args.combo), False
    if args.target == "keypress":
        return KeypressController(combo=args.combo), False
    cmd = args.cmd.split() if args.cmd else [sys.executable, "-m", "tempo.fake_ai"]
    ctrl = SubprocessController(cmd)
    ctrl.start()
    return ctrl, True


def main():
    ap = argparse.ArgumentParser(description="Not Quite My Tempo")
    ap.add_argument("--target", choices=["subprocess", "keypress", "app"], default="subprocess")
    ap.add_argument("--app", default="ChatGPT", help="macOS app name to focus + interrupt (with --target app)")
    ap.add_argument("--cmd", help="command to run as the interruptible target")
    ap.add_argument("--combo", default="esc", choices=["esc", "ctrl-c"])
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--debug", action="store_true", help="print live detector state")
    ap.add_argument("--headless", action="store_true",
                    help="no camera window -- run quietly in the background")
    args = ap.parse_args()

    controller, owns_proc = build_controller(args)
    detector = CutoffDetector()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Could not open camera {args.camera}", file=sys.stderr)
        sys.exit(1)

    flash = 0
    if args.headless:
        print(f"Running in background. Fist-cut by your face stops {args.app} "
              f"when it's focused. Ctrl+C to quit.")
    else:
        print("Ready. Raise a fist by your face, then cut sideways. 'q' to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            results, state = detector.process(rgb)

            if not args.headless and results.multi_hand_landmarks:
                for lm in results.multi_hand_landmarks:
                    mp_draw.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)

            if args.debug:
                sys.stdout.write(
                    f"\rface={'Y' if state.face else 'n'} "
                    f"hand={'Y' if state.hand else 'n'} "
                    f"byface={'Y' if state.near_face else 'n'} "
                    f"hold={'Y' if state.holding else 'n'} "
                    f"cut={state.velocity:5.2f} "
                    f"fired={'YES' if state.fired else '   '}   "
                )
                sys.stdout.flush()

            if state.fired:
                controller.stop()
                flash = 18
                if owns_proc and not controller.alive():
                    controller.restart()

            if args.headless:
                continue  # no window; Ctrl+C to quit

            draw_hud(frame, state, flash)
            flash = max(0, flash - 1)

            cv2.imshow("Not Quite My Tempo", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        detector.close()
        cap.release()
        cv2.destroyAllWindows()
        if owns_proc:
            controller.stop()
        if args.debug:
            print()


if __name__ == "__main__":
    main()
