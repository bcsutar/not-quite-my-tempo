"""PyInstaller entry point for the menu bar application."""

import logging

from tempo.tray import main


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.getLogger(__name__).exception("Fatal tray startup error")
        raise
