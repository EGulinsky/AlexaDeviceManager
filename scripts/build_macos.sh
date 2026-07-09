#!/bin/bash
set -euo pipefail

APP_NAME="Alexa Device Manager"
BUNDLE_ID="com.alexa-device-manager"
VERSION="2.0.0"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Clean up
rm -rf build dist

# Create virtual environment and install dependencies
python3 -m venv build_venv
source build_venv/bin/activate
pip install --quiet pyinstaller pyside6 qasync

# Build with PyInstaller
pyinstaller \
    --windowed \
    --onefile \
    --name "$APP_NAME" \
    --add-data "resources/icons:icons" \
    --osx-bundle-identifier "$BUNDLE_ID" \
    --icon resources/alexa_device_manager.icns \
    --distpath dist \
    --workpath build \
    run.py

# Create DMG
if command -v create-dmg &> /dev/null; then
    create-dmg \
        --volname "$APP_NAME" \
        --icon "$APP_NAME.app" 120 120 \
        --app-drop-link 360 120 \
        --window-pos 200 120 \
        --window-size 480 320 \
        --hide-extension "$APP_NAME.app" \
        "dist/$APP_NAME.dmg" \
        "dist/$APP_NAME.app"
fi

# Deactivate and clean
deactivate
rm -rf build_venv build

echo "Build complete: dist/$APP_NAME.app"
echo "DMG: dist/$APP_NAME.dmg"
