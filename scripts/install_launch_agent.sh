#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
PLIST_PATH="$HOME/Library/LaunchAgents/com.bcsutar.not-quite-my-tempo.plist"

python3.12 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -e "$REPO_DIR"

mkdir -p "$HOME/Library/Logs/NotQuiteMyTempo" "$HOME/Library/LaunchAgents"
sed \
  -e "s|__REPO_DIR__|$REPO_DIR|g" \
  -e "s|__VENV_DIR__|$VENV_DIR|g" \
  -e "s|__HOME__|$HOME|g" \
  "$REPO_DIR/scripts/com.bcsutar.not-quite-my-tempo.plist.template" \
  > "$PLIST_PATH"

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl enable "gui/$(id -u)/com.bcsutar.not-quite-my-tempo"

echo "Installed and started $PLIST_PATH"
