#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_VENV="$REPO_DIR/.build-venv"
DIST_DIR="$REPO_DIR/dist"
APP_NAME="Not Quite My Tempo.app"
DMG_NAME="Not-Quite-My-Tempo.dmg"
VOLUME_NAME="Not Quite My Tempo Installer"
APP_BUNDLE="$DIST_DIR/$APP_NAME"
DMG_PATH="$DIST_DIR/$DMG_NAME"
RW_DMG_PATH="$DIST_DIR/Not-Quite-My-Tempo-temp.dmg"
BUNDLE_ID="${BUNDLE_ID:-com.bcsutar.not-quite-my-tempo}"
APP_VERSION="${APP_VERSION:-1.0.0}"
MOUNT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/not-quite-my-tempo-dmg.XXXXXX")"

CODESIGN_IDENTITY="${CODESIGN_IDENTITY:-}"
NOTARY_PROFILE="${NOTARY_PROFILE:-}"
ENTITLEMENTS_PATH="${CODESIGN_ENTITLEMENTS:-$REPO_DIR/scripts/entitlements.plist}"

cleanup() {
  hdiutil detach "$MOUNT_DIR" -force -quiet 2>/dev/null || true
  rmdir "$MOUNT_DIR" 2>/dev/null || true
}
trap cleanup EXIT

python3.12 -m venv "$BUILD_VENV"
source "$BUILD_VENV/bin/activate"
python -m pip install --upgrade pip
python -m pip install -e "$REPO_DIR" pyinstaller

rm -rf "$REPO_DIR/build" "$DIST_DIR"
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Not Quite My Tempo" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --collect-data mediapipe \
  "$REPO_DIR/tray_launcher.py"

/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" \
  "$APP_BUNDLE/Contents/Info.plist" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Set :LSUIElement true" \
    "$APP_BUNDLE/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $APP_VERSION" \
  "$APP_BUNDLE/Contents/Info.plist" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $APP_VERSION" \
    "$APP_BUNDLE/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $APP_VERSION" \
  "$APP_BUNDLE/Contents/Info.plist" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $APP_VERSION" \
    "$APP_BUNDLE/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :NSCameraUsageDescription string Not Quite My Tempo uses your camera to detect the cutoff gesture" \
  "$APP_BUNDLE/Contents/Info.plist" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Set :NSCameraUsageDescription Not Quite My Tempo uses your camera to detect the cutoff gesture" \
    "$APP_BUNDLE/Contents/Info.plist"

if [[ -n "$CODESIGN_IDENTITY" ]]; then
  codesign --force --timestamp --options runtime --deep \
    --entitlements "$ENTITLEMENTS_PATH" \
    --sign "$CODESIGN_IDENTITY" "$APP_BUNDLE"
else
  # Ad-hoc signing keeps local builds launchable after removing download
  # quarantine, while Developer ID signing remains available for releases.
  codesign --force --deep --entitlements "$ENTITLEMENTS_PATH" \
    --sign - "$APP_BUNDLE"
fi
codesign --verify --deep --strict "$APP_BUNDLE"

STAGE_DIR="$DIST_DIR/dmg"
mkdir -p "$STAGE_DIR"
cp -R "$APP_BUNDLE" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

hdiutil create -volname "$VOLUME_NAME" -srcfolder "$STAGE_DIR" \
  -ov -fs HFS+ -format UDZO "$DMG_PATH"

if [[ -n "$CODESIGN_IDENTITY" ]]; then
  codesign --force --timestamp --sign "$CODESIGN_IDENTITY" "$DMG_PATH"
fi

if [[ -n "$CODESIGN_IDENTITY" && -n "$NOTARY_PROFILE" ]]; then
  xcrun notarytool submit "$DMG_PATH" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG_PATH"
  xcrun stapler validate "$DMG_PATH"
fi

echo "Built $DMG_PATH"
