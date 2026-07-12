"""Fletcher-cutoff gesture detection: hand-by-face, then a sideways cut.

Straight out of *Whiplash*: raise the hand up next to your face (the "hold"),
then snap it sideways/away to cut the band off.

Detection stages (heuristic, no trained gesture model):
  1. FACE: MediaPipe Face Detection gives a face box each frame.
  2. HOLD: a hand is raised next to the face -- its wrist is near the face box
     (within NEAR_FACE_RADIUS, measured in face-widths) and at roughly face
     height. A LOOSE fist check is applied (tolerant of hand angle).
  3. CUT: once a hold has been seen, the hand moves sharply AWAY from the face
     centre (outward horizontal speed exceeds CUT_SPEED).

Fires when a held-by-face hand cuts outward, sustained briefly, past a
cooldown debounce.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import mediapipe as mp

if not hasattr(mp, "solutions"):
    raise ImportError(
        "This project uses MediaPipe's classic `mp.solutions` API. "
        "Your installed build doesn't expose it (0.10.30+ dropped it). "
        "Install a compatible version on Python 3.12:\n"
        "    pip install 'mediapipe==0.10.14'\n"
    )

mp_hands = mp.solutions.hands
mp_face = mp.solutions.face_detection

# --- tunables -------------------------------------------------------------
NEAR_FACE_RADIUS = 1.6   # how close the hand must be to the face, in face-widths
HOLD_GRACE_S = 0.8       # after a hold, you have this long to complete the cut
CUT_SPEED = 0.5          # outward horizontal speed (face-widths / sec) to fire
MIN_SUSTAIN_S = 0.05     # cut must persist this long -> rejects twitches
COOLDOWN_S = 1.5         # ignore new fires for this long after one triggers
HISTORY = 6              # frames kept for velocity smoothing
FIST_CURL_MIN = 2        # LOOSE fist: at least this many fingers curled (of 4)
FIST_MARGIN = 0.04       # tolerant curl threshold
# -------------------------------------------------------------------------

WRIST = 0
FINGERS = [(8, 6), (12, 10), (16, 14), (20, 18)]  # (tip, pip)


def _dist(a, b) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def loose_fist(landmarks) -> bool:
    """Tolerant fist check: at least FIST_CURL_MIN fingers curled inward."""
    wrist = landmarks[WRIST]
    curled = 0
    for tip_i, pip_i in FINGERS:
        if _dist(landmarks[tip_i], wrist) < _dist(landmarks[pip_i], wrist) + FIST_MARGIN:
            curled += 1
    return curled >= FIST_CURL_MIN


@dataclass
class DetectorState:
    face: bool = False          # a face is detected
    hand: bool = False          # a hand is detected
    near_face: bool = False     # hand is up next to the face
    holding: bool = False       # a valid hold is currently active / in grace
    velocity: float = 0.0       # outward horizontal speed (face-widths/sec)
    fired: bool = False         # fired on THIS frame
    direction: str = ""         # "left" / "right"
    last_fire_t: float = 0.0
    _hold_seen_t: float = 0.0
    _sustain_start: float = 0.0
    _samples: deque = field(default_factory=lambda: deque(maxlen=HISTORY))


class CutoffDetector:
    """Feeds RGB frames in, reports when the by-face cut fires."""

    def __init__(self):
        self.hands = mp_hands.Hands(
            model_complexity=0, max_num_hands=1,
            min_detection_confidence=0.6, min_tracking_confidence=0.5,
        )
        self.face = mp_face.FaceDetection(
            model_selection=0, min_detection_confidence=0.6,
        )
        self.state = DetectorState()

    def close(self):
        self.hands.close()
        self.face.close()

    def process(self, rgb_frame):
        now = time.time()
        s = self.state
        s.fired = False

        # --- face box (normalised) ---
        fres = self.face.process(rgb_frame)
        face_cx = face_cy = face_w = None
        if fres.detections:
            box = fres.detections[0].location_data.relative_bounding_box
            face_w = box.width
            face_cx = box.xmin + box.width / 2
            face_cy = box.ymin + box.height / 2
        s.face = face_cx is not None

        # --- hand wrist (normalised) ---
        hres = self.hands.process(rgb_frame)
        wrist_x = wrist_y = None
        s.hand = False
        fist_ok = False
        if hres.multi_hand_landmarks:
            lm = hres.multi_hand_landmarks[0].landmark
            wrist_x, wrist_y = lm[WRIST].x, lm[WRIST].y
            s.hand = True
            fist_ok = loose_fist(lm)

        # --- is the hand up next to the face? ---
        s.near_face = False
        if s.face and s.hand and face_w and face_w > 1e-3:
            d = ((wrist_x - face_cx) ** 2 + (wrist_y - face_cy) ** 2) ** 0.5
            s.near_face = (d / face_w) <= NEAR_FACE_RADIUS and fist_ok

        if s.near_face:
            s._hold_seen_t = now
        s.holding = (now - s._hold_seen_t) <= HOLD_GRACE_S

        # --- outward horizontal speed, measured in face-widths/sec ---
        s._samples.append((now, wrist_x, face_cx, face_w))
        signed_v = self._outward_velocity()  # + = moving away from face centre
        s.velocity = signed_v

        cutting = s.holding and s.hand and signed_v > CUT_SPEED
        if cutting:
            if s._sustain_start == 0.0:
                s._sustain_start = now
            elif (now - s._sustain_start) >= MIN_SUSTAIN_S:
                if (now - s.last_fire_t) >= COOLDOWN_S:
                    s.fired = True
                    s.last_fire_t = now
                    s._sustain_start = 0.0
                    s._hold_seen_t = 0.0  # require a fresh hold next time
                    # direction: which side of the face the hand went
                    s.direction = "right" if (wrist_x or 0) > (face_cx or 0.5) else "left"
        else:
            s._sustain_start = 0.0

        return hres, s

    def _outward_velocity(self) -> float:
        """Speed of the hand moving AWAY from the face centre, in face-widths/sec.

        Using distance-from-face (not raw x) means a cut in either direction
        reads as positive, and normalising by face width makes it independent
        of how close you are to the camera.
        """
        pts = [(t, wx, fcx, fw) for (t, wx, fcx, fw) in self.state._samples
               if wx is not None and fcx is not None and fw and fw > 1e-3]
        if len(pts) < 2:
            return 0.0
        (t0, wx0, fcx0, fw0) = pts[0]
        (t1, wx1, fcx1, fw1) = pts[-1]
        dt = t1 - t0
        if dt <= 0:
            return 0.0
        # horizontal offset from face centre, in face-widths, at each end
        off0 = abs(wx0 - fcx0) / fw0
        off1 = abs(wx1 - fcx1) / fw1
        return (off1 - off0) / dt
