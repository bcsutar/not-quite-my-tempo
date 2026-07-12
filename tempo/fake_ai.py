"""A self-contained fake "AI" that streams tokens forever.

This exists so anyone can clone the repo and see the whole thing work WITHOUT
API keys or a browser. The main app launches this as a subprocess and cuts it
off with SIGINT when you make the gesture. On Ctrl+C it prints a huffy little
message and exits -- exactly what you want in the demo GIF.
"""

import sys
import time

FILLER = (
    "Sure! Here is a long, rambling, over-eager explanation that goes on and "
    "on and on, padding every point with three unnecessary clauses, circling "
    "back to restate what was already said, and generally refusing to stop "
    "until someone physically intervenes... "
)


def main():
    print("\n[AI] thinking", flush=True)
    time.sleep(0.4)
    try:
        i = 0
        for word in (FILLER * 50).split(" "):
            sys.stdout.write(word + " ")
            sys.stdout.flush()
            i += 1
            if i % 12 == 0:
                sys.stdout.write("\n")
            time.sleep(0.08)
    except KeyboardInterrupt:
        print("\n\n[AI] ...okay, okay! Stopping. That was NOT quite your tempo.")
        sys.exit(0)
    print("\n[AI] done.")


if __name__ == "__main__":
    main()
