"""Quick camera sanity check. Run BEFORE the main app:

    python check_camera.py            # tries camera index 0
    python check_camera.py 1          # tries index 1

Opens the webcam, grabs a few frames, prints resolution, and shows a preview
window for ~2 seconds. If this works, `python -m tempo.main` will too.
"""
import sys, time
import cv2

idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
cap = cv2.VideoCapture(idx)
if not cap.isOpened():
    print(f"❌ Could not open camera {idx}. Try another index (0/1/2) "
          f"or check OS camera permissions.")
    sys.exit(1)

ok, frame = cap.read()
if not ok:
    print(f"❌ Opened camera {idx} but couldn't read a frame.")
    cap.release(); sys.exit(1)

h, w = frame.shape[:2]
print(f"✅ Camera {idx} works — {w}x{h}. Showing a 2s preview...")
t0 = time.time()
while time.time() - t0 < 2.0:
    ok, frame = cap.read()
    if not ok: break
    cv2.imshow("camera check (closes automatically)", cv2.flip(frame, 1))
    if cv2.waitKey(1) & 0xFF == ord("q"): break
cap.release(); cv2.destroyAllWindows()
print("Done. If you saw yourself, you're ready: python -m tempo.main")
