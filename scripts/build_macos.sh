#!/bin/bash
set -euo pipefail

APP_NAME="Alexa Device Manager"
BUNDLE_ID="com.alexa-device-manager"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Bump build number in _version.py
python3 << 'PYEOF'
import re
path = 'app/_version.py'
ns = {}
exec(open(path).read(), ns)
cur = ns['VERSION']
new = re.sub(r'build\.(\d+)', lambda m: f'build.{int(m.group(1))+1}', cur)
print(f'Version: {cur} -> {new}')
with open(path, 'w') as f:
    f.write(f"VERSION = '{new}'\n")
PYEOF

# Read the bumped version
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

# Copy to Applications
rm -rf "/Applications/$APP_NAME.app"
cp -R "dist/$APP_NAME.app" "/Applications/$APP_NAME.app"

echo "Build complete: dist/$APP_NAME.app (version $VERSION)"
echo "Installed: /Applications/$APP_NAME.app"
