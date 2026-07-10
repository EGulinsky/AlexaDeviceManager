#!/bin/bash
set -euo pipefail

APP_NAME="Alexa Device Manager"
VERSION="2.0.0"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

rm -rf build dist

python3 -m venv build_venv
source build_venv/bin/activate
pip install --quiet pyinstaller pyside6 qasync

ICON_OPT=""
if [ -f "resources/icon.ico" ]; then
    ICON_OPT="--icon resources/icon.ico"
fi

pyinstaller \
    --windowed \
    --onefile \
    --name "$APP_NAME" \
    $ICON_OPT \
    --distpath dist \
    --workpath build \
    run.py

deactivate
rm -rf build_venv build

echo "Build complete: dist/$APP_NAME.exe"
