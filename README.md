# Alexa Device Manager

A cross-platform desktop app for managing Amazon Alexa smart home devices: list,
batch-delete unresponsive or unwanted devices, organize devices into groups, and
inspect the raw data Alexa has for each device.

Built on top of Amazon's undocumented, reverse-engineered internal APIs since Amazon has deprecated
the web UI for managing smart home devices and the mobile app is tedious for
bulk operations.

> [!WARNING]
> **Unofficial and unsupported.** This project is **not affiliated with,
> endorsed by, or supported by Amazon.com, Inc.** or its affiliates. "Alexa",
> "Echo", and "Amazon" are trademarks of Amazon.com, Inc. or its affiliates.
>
> The app talks to internal, undocumented Amazon endpoints that are not part of
> any public API and can change or stop working at any time without notice.
> Using it may be subject to Amazon's Terms of Service. **Use at your own
> risk** — the author assumes no responsibility for any consequences of using
> this software, including but not limited to account restrictions or data loss.
> See the [LICENSE](LICENSE) for the full "as is", no-warranty terms.

## Features

- List all Alexa smart home devices, grouped by integration/skill or by device type
- Sortable table (name, type, integration, online/offline status, applianceId)
- Batch-delete devices — all unresponsive ones, or any manual selection
- Full management of Alexa "Groups": create, rename, delete, and move devices
  between them (via menu or drag & drop)
- Per-device online/offline status (via the `Reachability` feature)
- Client-side icons per device type/category (Amazon's API doesn't expose icons)
- A built-in GraphQL schema explorer ("Check Fields") for further reverse-engineering
- Cross-platform: runs on **macOS, Windows, and Linux** from the same codebase

## Requirements

- **Python 3.11+**
- PySide6 (Qt6 for Python) — installed automatically via pip

## Quick Start

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m app.main
```

Or on macOS simply:

```sh
./run.sh
```

## How it works

There's no OAuth or API key involved. The app embeds a `QWebEngineView` (Qt's
Chromium-based WebEngine), has you sign in to your Amazon account normally
(including 2FA), and then makes `fetch()` calls to Amazon's internal GraphQL
endpoint (`/nexus/v1/graphql`) and REST endpoints (`/api/phoenix/appliance/...`)
from *inside* that authenticated page — the same way the official Alexa web app
does. No credentials are ever stored or transmitted by the app itself beyond the
standard browser session cookies the WebEngine already manages.

The `applianceId` format, region/host selection, and other implementation details are documented in the source code under `app/models/` and `app/session.py`.

## Building for Distribution

### macOS (.app + DMG)

```sh
pip install pyinstaller
pyinstaller --windowed --onefile --name "Alexa Device Manager" \
  --icon resources/alexa_device_manager.icns app/main.py
# Create DMG:
hdiutil create -volname "Alexa Device Manager" \
  -srcfolder dist/Alexa\ Device\ Manager.app \
  -ov -format UDZO dist/AlexaDeviceManager.dmg
```

Or use `brew install --cask alexa-device-manager` (once published).

### Windows (.exe)

```sh
pyinstaller --windowed --onefile --name "Alexa Device Manager" \
  --icon resources/icon.ico app/main.py
```

### Linux (.AppImage)

```sh
pyinstaller --windowed --onefile --name "alexa-device-manager" \
  --icon resources/icon.png app/main.py
```

## Project Structure

```
AlexaDeviceManager/
├── app/
│   ├── main.py                   # Entry point
│   ├── main_window.py            # QMainWindow with splitter + toolbar
│   ├── session.py                # QWebEngineView + JS fetch bridge
│   ├── login_dialog.py           # Amazon login dialog
│   ├── device_list_view.py       # QTableView with sort + drag
│   ├── sidebar.py                # QTreeWidget for filters + groups
│   ├── batch_bar.py              # QToolBar for batch actions
│   ├── view_model.py             # Business logic
│   ├── store.py                  # JSON persistence
│   └── models/                   # Data models
│       ├── device.py
│       ├── device_group.py
│       ├── appliance_id.py       # ApplianceId parser (base64 decode)
│       ├── region.py
│       ├── filter.py
│       └── lookup_tables.py      # Display categories + HA domains
├── resources/
│   └── alexa_device_manager.icns
├── scripts/
│   ├── build_macos.sh
│   └── alexa-device-manager.rb   # Homebrew Cask formula
├── requirements.txt
└── pyproject.toml
```

## License

[MIT](LICENSE)
