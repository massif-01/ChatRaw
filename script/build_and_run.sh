#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
PRODUCT_NAME="ChatRawMac"
APP_NAME="ChatRaw for Mac"
BUNDLE_ID="com.massif.ChatRawMac"
APP_VERSION="2.2"
APP_BUILD="220"
MIN_SYSTEM_VERSION="14.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
LEGACY_APP_BUNDLE="$DIST_DIR/$PRODUCT_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_BINARY="$APP_MACOS/$PRODUCT_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
APP_ICON_SOURCE="$ROOT_DIR/Sources/ChatRawMac/Resources/AppIcon.icns"
APP_ICON_NAME="AppIcon.icns"
BACKEND_LAUNCHER="$ROOT_DIR/script/backend_launcher.py"
BACKEND_RUNTIME_DIR="$DIST_DIR/ChatRawBackend"
DMG_STAGING_DIR="$DIST_DIR/dmg-staging"
DMG_PATH="$DIST_DIR/ChatRaw-for-Mac-$APP_VERSION.dmg"
VENV_DIR="$ROOT_DIR/venv"
PYTHON_BOOTSTRAP="${PYTHON_BOOTSTRAP:-python3}"
REQ_FILE="$ROOT_DIR/backend/requirements.txt"
REQ_STAMP="$VENV_DIR/.chatraw-requirements.sha256"
STATUS_DIR="$HOME/Library/Application Support/ChatRawMac"
STATUS_FILE="$STATUS_DIR/backend-status.json"

usage() {
  echo "usage: $0 [run|--debug|--logs|--telemetry|--verify|--dmg]" >&2
}

ensure_backend_env() {
  if ! "$PYTHON_BOOTSTRAP" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
    echo "Python 3.11+ is required to create the backend environment." >&2
    echo "Set PYTHON_BOOTSTRAP=/path/to/python3.11-or-newer and retry." >&2
    exit 1
  fi

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BOOTSTRAP" -m venv "$VENV_DIR"
  fi

  local req_hash
  req_hash="$(shasum -a 256 "$REQ_FILE" | awk '{print $1}')"

  if [[ ! -f "$REQ_STAMP" ]] || [[ "$(cat "$REQ_STAMP")" != "$req_hash" ]]; then
    "$VENV_DIR/bin/python" -m pip install --upgrade pip
    "$VENV_DIR/bin/python" -m pip install -r "$REQ_FILE"
    echo "$req_hash" > "$REQ_STAMP"
  fi

  if ! backend_import_check; then
    "$VENV_DIR/bin/python" -m pip install --upgrade --force-reinstall -r "$REQ_FILE"
    echo "$req_hash" > "$REQ_STAMP"
    backend_import_check
  fi
}

backend_import_check() {
  "$VENV_DIR/bin/python" -X faulthandler -c 'import faulthandler; faulthandler.dump_traceback_later(60, exit=True); import fastapi, uvicorn, aiohttp, certifi, pydantic, pypdf, docx, trafilatura' >/dev/null
}

build_backend_runtime() {
  if ! "$VENV_DIR/bin/python" -c 'import PyInstaller' >/dev/null 2>&1; then
    "$VENV_DIR/bin/python" -m pip install pyinstaller
  fi

  "$VENV_DIR/bin/python" -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --name ChatRawBackend \
    --distpath "$DIST_DIR" \
    --workpath "$ROOT_DIR/build/pyinstaller" \
    --specpath "$ROOT_DIR/build/pyinstaller" \
    --add-data "$ROOT_DIR/backend:backend" \
    --add-data "$ROOT_DIR/Plugins:Plugins" \
    --collect-all certifi \
    --collect-all trafilatura \
    --collect-all babel \
    --collect-all dateparser \
    --hidden-import backend.main \
    "$BACKEND_LAUNCHER"
}

stage_app_bundle() {
  local include_backend="${1:-false}"
  local configuration="${2:-debug}"

  swift build -c "$configuration"
  local build_binary
  build_binary="$(swift build -c "$configuration" --show-bin-path)/$PRODUCT_NAME"

  rm -rf "$APP_BUNDLE" "$LEGACY_APP_BUNDLE"
  mkdir -p "$APP_MACOS" "$APP_RESOURCES"
  cp "$build_binary" "$APP_BINARY"
  chmod +x "$APP_BINARY"
  cp "$APP_ICON_SOURCE" "$APP_RESOURCES/$APP_ICON_NAME"
  if [[ "$include_backend" == "true" ]]; then
    rm -rf "$APP_RESOURCES/ChatRawBackend"
    cp -R "$BACKEND_RUNTIME_DIR" "$APP_RESOURCES/ChatRawBackend"
  fi

  cat >"$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>$PRODUCT_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleShortVersionString</key>
  <string>$APP_VERSION</string>
  <key>CFBundleVersion</key>
  <string>$APP_BUILD</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon.icns</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>$MIN_SYSTEM_VERSION</string>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
  </dict>
</dict>
</plist>
PLIST

  codesign --force --deep --sign - "$APP_BUNDLE"
}

create_dmg() {
  rm -rf "$DMG_STAGING_DIR" "$DMG_PATH"
  mkdir -p "$DMG_STAGING_DIR"
  cp -R "$APP_BUNDLE" "$DMG_STAGING_DIR/"
  ln -s /Applications "$DMG_STAGING_DIR/Applications"
  hdiutil create \
    -volname "$APP_NAME $APP_VERSION" \
    -srcfolder "$DMG_STAGING_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"
  echo "$DMG_PATH"
}

open_app() {
  mkdir -p "$STATUS_DIR"
  rm -f "$STATUS_FILE"
  /usr/bin/open -n "$APP_BUNDLE"
}

verify_app() {
  open_app

  for _ in $(seq 1 160); do
    if [[ -f "$STATUS_FILE" ]]; then
      if grep -q '"state"[[:space:]]*:[[:space:]]*"ready"' "$STATUS_FILE"; then
        pgrep -x "$PRODUCT_NAME" >/dev/null
        return 0
      fi
      if grep -q '"state"[[:space:]]*:[[:space:]]*"failed"' "$STATUS_FILE"; then
        cat "$STATUS_FILE" >&2
        return 1
      fi
    fi
    sleep 0.25
  done

  echo "Timed out waiting for ChatRaw backend readiness." >&2
  if [[ -f "$STATUS_FILE" ]]; then
    cat "$STATUS_FILE" >&2
  fi
  return 1
}

pkill -x "$PRODUCT_NAME" >/dev/null 2>&1 || true
ensure_backend_env

case "$MODE" in
  run)
    stage_app_bundle false
    open_app
    ;;
  --debug|debug)
    stage_app_bundle false
    lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    stage_app_bundle false
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$PRODUCT_NAME\""
    ;;
  --telemetry|telemetry)
    stage_app_bundle false
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    stage_app_bundle false
    verify_app
    ;;
  --dmg|dmg)
    build_backend_runtime
    stage_app_bundle true release
    create_dmg
    ;;
  *)
    usage
    exit 2
    ;;
esac
