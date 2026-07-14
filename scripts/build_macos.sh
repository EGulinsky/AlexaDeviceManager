#!/bin/bash
set -euo pipefail

APP_NAME="Alexa Device Manager"
BUNDLE_ID="com.alexa-device-manager"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Read the version tracked in source; release automation should update it explicitly.
VERSION=$(python3 -c "exec(open('app/_version.py').read()); print(VERSION)")

# Clean up
rm -rf build dist

# Create virtual environment and install dependencies
python3 -m venv build_venv
source build_venv/bin/activate
pip install --quiet pyinstaller pyside6 qasync

# Build with PyInstaller
pyinstaller \
    --windowed \
    --onedir \
    --name "$APP_NAME" \
    --osx-bundle-identifier "$BUNDLE_ID" \
    --icon resources/alexa_device_manager.icns \
    --distpath dist \
    --workpath build \
    run.py

# Deactivate and clean
deactivate
rm -rf build_venv build

echo "Build complete: dist/$APP_NAME.app (version $VERSION)"
