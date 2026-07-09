#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="Alexa Device Manager"

echo "=== Build ==="
bash scripts/build_macos.sh

echo "=== Version & Sign ==="
plutil -replace CFBundleShortVersionString -string "2.0.0" "dist/$APP_NAME.app/Contents/Info.plist"
plutil -replace CFBundleVersion -string "2.0.0" "dist/$APP_NAME.app/Contents/Info.plist"
codesign -f -s - "dist/$APP_NAME.app"

echo "=== Deploy to /Applications ==="
cp -Rf "dist/$APP_NAME.app" /Applications/

echo "=== Git: stage all ==="
git add -A

if ! git diff --cached --quiet; then
    git commit -m "WIP"
    unset GH_TOKEN
    git push
    echo "=== Committed & pushed ==="
else
    echo "=== No changes to commit ==="
fi
