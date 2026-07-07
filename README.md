# Alexa Device Manager

A native macOS app for managing Amazon Alexa smart home devices: list, batch-delete
unresponsive or unwanted devices, organize devices into groups, and inspect the raw
data Alexa has for each device.

Built on top of Amazon's undocumented, reverse-engineered internal APIs (see
[NOTES.md](NOTES.md) for the full technical writeup) since Amazon has deprecated the
web UI for managing smart home devices and the mobile app is tedious for bulk
operations.

> [!WARNING]
> **Unofficial and unsupported.** This project is **not affiliated with, endorsed by,
> or supported by Amazon.com, Inc.** or its affiliates. "Alexa", "Echo", and "Amazon"
> are trademarks of Amazon.com, Inc. or its affiliates.
>
> The app talks to internal, undocumented Amazon endpoints that are not part of any
> public API and can change or stop working at any time without notice. Using it may
> be subject to Amazon's Terms of Service. **Use at your own risk** — the author
> assumes no responsibility for any consequences of using this software, including
> but not limited to account restrictions or data loss. See the [LICENSE](LICENSE)
> for the full "as is", no-warranty terms.

## Features

- List all Alexa smart home devices, grouped by integration/skill or by device type
- Sortable table (name, type, integration, online/offline status, applianceId)
- Batch-delete devices — all unresponsive ones, or any manual selection
- Full management of Alexa "Groups": create, rename, delete, and move devices
  between them (via menu or drag & drop, including multi-selection)
- Per-device online/offline status (via the `Reachability` feature, since there's no
  simple top-level `connectivity` field on this API)
- Client-side icons per device type/category (Amazon's API doesn't expose brand
  logos or icons)
- A built-in GraphQL schema explorer ("Check Fields") for further reverse-engineering
  without leaving the app
- An XCTest target that runs live GraphQL queries against your already-authenticated
  session, for scripted schema research without manual clicking

## Requirements

- macOS 14 (Sonoma) or later
- Xcode 15+
- [XcodeGen](https://github.com/yonaskolb/XcodeGen) (`brew install xcodegen`) — used
  to generate the `.xcodeproj` from `Xcode/project.yml`; the generated project file
  itself is not committed

## Building

Quick compile check (Swift Package Manager, no signed app bundle):

```sh
swift build
```

Full signed app bundle (what you actually want to run):

```sh
cd Xcode
xcodegen generate
xcodebuild -project AlexaDeviceManager.xcodeproj -scheme AlexaDeviceManager \
  -destination 'platform=macOS' -allowProvisioningUpdates build
```

Then open the built `.app` from
`~/Library/Developer/Xcode/DerivedData/AlexaDeviceManager-*/Build/Products/Debug/`,
or open `Xcode/AlexaDeviceManager.xcodeproj` in Xcode and run it from there. You'll
need to set your own Apple Developer Team ID in `Xcode/project.yml`
(`DEVELOPMENT_TEAM`) for code signing.

## How it works

There's no OAuth or API key involved. The app embeds a `WKWebView`, has you sign in
to your Amazon account normally (including 2FA), and then makes `fetch()` calls to
Amazon's internal GraphQL endpoint (`/nexus/v1/graphql`) and REST endpoints
(`/api/phoenix/appliance/...`) from *inside* that authenticated page — the same way
the official Alexa web app does. No credentials are ever stored or transmitted by the
app itself beyond the standard browser session cookies WebKit already manages.

See [NOTES.md](NOTES.md) for the full API reverse-engineering notes, including the
`applianceId` format, region/host selection, and known limitations.

## License

[MIT](LICENSE)
