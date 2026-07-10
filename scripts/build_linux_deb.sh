#!/bin/bash
set -euo pipefail

APP_NAME="alexa-device-manager"
VERSION="2.0.0"
PKG_NAME="${APP_NAME}_${VERSION}_amd64"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Build the binary first
bash scripts/build_linux.sh

# Prepare .deb package directory
DEB_DIR="dist/$PKG_NAME"
mkdir -p "$DEB_DIR/DEBIAN"
mkdir -p "$DEB_DIR/usr/bin"
mkdir -p "$DEB_DIR/usr/share/applications"
mkdir -p "$DEB_DIR/usr/share/icons/hicolor/128x128/apps"

# Copy the executable
cp "dist/$APP_NAME" "$DEB_DIR/usr/bin/$APP_NAME"

# Create control file
cat > "$DEB_DIR/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Eugen Gulinsky
Description: Cross-platform desktop app for managing Amazon Alexa smart home devices
 List, batch-delete unresponsive or unwanted devices, organize devices into
 groups, and inspect raw device data via Amazon's internal APIs.
Depends: python3 (>= 3.11), python3-pyside6
EOF

# Create .desktop entry
cat > "$DEB_DIR/usr/share/applications/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=Alexa Device Manager
Comment=Manage Amazon Alexa smart home devices
Exec=$APP_NAME
Type=Application
Categories=Utility;
Terminal=false
EOF

# Copy icon if available
if [ -f "resources/icon.png" ]; then
    cp "resources/icon.png" "$DEB_DIR/usr/share/icons/hicolor/128x128/apps/$APP_NAME.png"
fi

# Build the .deb
dpkg-deb --build "$DEB_DIR"

echo "Build complete: dist/$PKG_NAME.deb"
