"""Headless self-test: proves the fist + sideways-cut gesture logic and the
SIGINT interrupt work WITHOUT a camera. Run this first:

    python selftest.py
"""
import os, signal, subprocess, sys, time
from collections import deque

VT, SUSTAIN, COOL, HIST, MARGIN = 1.3, 0.06, 1.5, 6, 0.02
WRIST = 0
FINGERS = [(8, 6), (12, 10), (16, 14), (20, 18)]


class P:
    def __init__(s, x, y): s.x = x; s.y = y


def dist(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def is_fist(lm):
    w = lm[WRIST]; curled = 0
    for t, p in FINGERS:
        if dist(lm[t], w) < dist(lm[p], w) + MARGIN:
            curled += 1
    return curled >= 3


def make_hand(wx, fist):
    lm = [P(0, 0) for _ in range(21)]
    lm[WRIST] = P(wx, 0.5)
    for tip, pip in FINGERS:
        if fist:
            lm[pip] = P(wx + 0.10, 0.5); lm[tip] = P(wx + 0.05, 0.5)
        else:
            lm[pip] = P(wx + 0.05, 0.5); lm[tip] = P(wx + 0.12, 0.5)
    return lm


class St:
    def __init__(s):
        s.v = 0; s.fist = False; s.arm = False; s.fire = False
        s.dir = ""; s.lf = -99; s.ss = 0; s.buf = deque(maxlen=HIST)


def vel(s):
    p = [(t, x) for t, x in s.buf if x is not None]
    if len(p) < 2: return 0.0
    (t0, x0), (t1, x1) = p[0], p[-1]; dt = t1 - t0
    return (x1 - x0) / dt if dt > 0 else 0.0


def step(s, lm, now):
    s.fire = False
    wx = lm[WRIST].x if lm else None
    s.fist = is_fist(lm) if lm else False
    s.buf.append((now, wx)); sv = vel(s); s.v = abs(sv)
    if s.fist and s.v > VT:
        if not s.arm: s.arm = True; s.ss = now
        elif now - s.ss >= SUSTAIN and now - s.lf >= COOL:
            s.fire = True; s.dir = "right" if sv > 0 else "left"
            s.lf = now; s.arm = False
    else:
        s.arm = False


def run(xs, fist, dt):
    s = St(); t = 0; fired = False; d = ""
    for x in xs:
        t += dt; step(s, make_hand(x, fist), t); fired |= s.fire
        if s.fire: d = s.dir
    return fired, d


ok = True

def check(name, got, want):
    global ok
    good = got == want; ok &= good
    print(f"[{'PASS' if good else 'FAIL'}] {name}: {got} (want {want})")

check("fist recognised",       is_fist(make_hand(0.5, True)),  True)
check("open hand not a fist",  is_fist(make_hand(0.5, False)), False)
check("fist cut right fires",  run([0.3,0.4,0.55,0.7,0.82,0.9], True, 0.05), (True, "right"))
check("fist cut left fires",   run([0.9,0.8,0.65,0.5,0.35,0.2], True, 0.05), (True, "left"))
check("open-hand swipe ignored", run([0.3,0.4,0.55,0.7,0.82,0.9], False, 0.05)[0], False)
check("fist held still ignored", run([0.5]*6, True, 0.05)[0], False)

# real SIGINT interrupt path
p = subprocess.Popen([sys.executable, "-m", "tempo.fake_ai"],
                     start_new_session=True,
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(1.0)
os.killpg(os.getpgid(p.pid), signal.SIGINT)
out, _ = p.communicate(timeout=5)
check("SIGINT interrupt path", p.returncode == 0 and "Stopping" in out, True)

print("\nALL GOOD \u2705" if ok else "\nSOMETHING FAILED \u274c")
sys.exit(0 if ok else 1)
