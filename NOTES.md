# Alexa Smart Home Device Management — Reverse-Engineered API

Notes for building a macOS app to manage (list/delete) Alexa smart home
devices. Based on reverse-engineered, **undocumented** internal Amazon
endpoints (not an official API — can break at any time without notice).

Source/inspiration: https://github.com/Shereef/Python-Delete-Alexa-Devices
(browser JS method from issue #9, by rPraml/Fade2Gray2, building on
Apollon77's `alexa-remote` project).

## Context / why this is needed

If you run your own Home Assistant Alexa smart home skill and repeatedly
change the entity filter in `configuration.yaml` (e.g. narrowing the domain
filter, adding/removing individual entities), Alexa ends up with **stale,
outdated devices** — Alexa's discovery is purely additive, there's no
rescan-with-deletion. Amazon has by now completely deprecated the web UI
(`alexa.amazon.com/spa/...`, now just shows a QR code for the phone app),
and manually deleting many devices in the iOS/Android app is tedious.

This method lets you talk directly to the internal Amazon APIs that the
app/web UI itself uses, via the logged-in browser session.

## Basic principle

Authentication runs entirely on **Amazon session cookies** (no OAuth bearer
token, no API key) — every request has to come from an origin where the
user is logged into Amazon in the browser (`credentials: 'include'`, or for
native apps: send along the cookie jar of the logged-in session).

### Host selection (region-dependent!)

You have to find the right Alexa region domain for the given account.
Candidates (try them in order to see which one returns JSON instead of a
login redirect):

- `https://alexa.amazon.de` (worked in testing — German account)
- `https://alexa.amazon.com`
- `https://pitangui.amazon.com` (US)
- `https://layla.amazon.com` (EU/UK — this is incidentally also the domain
  Amazon uses for the OAuth account-linking redirect URI in the EU market,
  in case that comes up in the context of an HA Alexa skill setup)
- `https://alexa.amazon.co.jp` (JP)

Test: `GET /api/behaviors/entities?skillId=amzn1.ask.1p.smarthome` — returns
a JSON response for the correct host + a logged-in session.

## 1. Listing devices (GraphQL, read-only)

```
POST https://<host>/nexus/v1/graphql
Content-Type: application/json
Accept: application/json

{
  "query": "query { endpoints { items { friendlyName legacyAppliance { applianceId } } } }"
}
```

Response:
```json
{
  "data": {
    "endpoints": {
      "items": [
        { "friendlyName": "Living Room Left", "legacyAppliance": { "applianceId": "SKILL_<base64>_cover#living_room_left" } },
        ...
      ]
    }
  }
}
```

Returns **all** smart home devices across **all** linked skills (not just
your own) — e.g. also Sonos, Echo, Ring, Hue devices etc. Important for the
app: filter by skill before deleting anything.

## 2. Decoding the `applianceId` format

Format: `SKILL_<base64-json>_<domain>#<entity_id-suffix>`

The base64 part decodes to JSON containing the skill ID:
```json
{"skillId": "amzn1.ask.skill.8d6c05ef-bb65-4bbd-adcf-0738fa8f8380", "stage": "development"}
```

The part after the `_` (e.g. `cover#living_room_left`) is, for Home
Assistant skills, exactly `<HA-domain>#<HA-object_id>` — it can be
translated 1:1 back into an HA `entity_id` (`domain.object_id`).

Swift pseudocode for decoding:
```swift
// applianceId e.g. "SKILL_eyJza2lsbElkIjoi...=_cover#living_room_left"
let parts = applianceId.split(separator: "_", maxSplits: 1)
// parts[0] == "SKILL"
// After that: everything up to the LAST "_" before the domain# part is the base64 block.
// A regex is more robust: ^SKILL_([A-Za-z0-9+/=]+)_(.+)$
let regex = /^SKILL_([A-Za-z0-9+/=]+)_(.+)$/
if let match = applianceId.firstMatch(of: regex) {
    let base64Part = match.1
    let suffix = match.2 // e.g. "cover#living_room_left"
    if let jsonData = Data(base64Encoded: String(base64Part)),
       let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: String] {
        let skillId = json["skillId"]
        let stage = json["stage"] // "development" or "live"
    }
}
```

Not every `applianceId` matches the `SKILL_...` format — some (other skill
types, native Amazon devices) have a different format. In the JS prototype
this was handled by returning `null` on a non-match.

## 3. Deleting a device

```
DELETE https://<host>/api/phoenix/appliance/<url-encoded-applianceId>
Accept: application/json
Content-Type: application/json
```

- The response is practically always `200 OK`, **even if nothing was
  actually deleted internally** — success can only be verified by listing
  again, not from the status code.
- Some accounts additionally need a `csrf` header (extractable from another
  Amazon request, e.g. a cart update on amazon.de/amazon.com). This
  **wasn't** needed in testing here — plain cookie auth was sufficient.

## 4. Tested example (browser console, JS)

```javascript
// List all devices
const res = await fetch('/nexus/v1/graphql', {
  method: 'POST',
  headers: {"Content-Type": "application/json", "Accept": "application/json"},
  body: JSON.stringify({query: `query { endpoints { items { friendlyName legacyAppliance { applianceId } } } }`})
});
const json = await res.json();
const items = json.data.endpoints.items;

// Filter by your own skill
const OUR_SKILL = 'amzn1.ask.skill.XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX';
function decodeSkill(applianceId) {
  const m = applianceId.match(/^SKILL_([A-Za-z0-9+/=]+)_(.+)$/);
  if (!m) return null;
  try { return JSON.parse(atob(m[1])); } catch (e) { return null; }
}
const ours = items.filter(it => {
  const info = decodeSkill(it.legacyAppliance.applianceId);
  return info && info.skillId === OUR_SKILL;
});

// Delete
for (const d of ours) {
  const r = await fetch(`/api/phoenix/appliance/${encodeURIComponent(d.legacyAppliance.applianceId)}`, {
    method: "DELETE",
    headers: { "Accept": "application/json", "Content-Type": "application/json" }
  });
  console.log(d.friendlyName, r.status);
}
```

Successfully tested (2026-07-05): listed 84 devices from an HA skill,
filtered, deleted all 84, then verified `0` remaining via another listing —
0 errors, all DELETE calls `200 OK`.

## Ideas for the macOS app architecture

1. **Login/session:** Load a `WKWebView` with the Amazon login page (e.g.
   `https://alexa.amazon.de`), the user logs in normally (including their
   own 2FA). Then read out cookies via
   `WKWebsiteDataStore.default().httpCookieStore`.
2. **API calls:** Put cookies into `URLSession` requests (`HTTPCookie` →
   `HTTPCookieStorage`, or manually as a `Cookie` header), hit the same
   endpoints as above.
3. **UI:** List of all devices grouped by skill (skill ID → readable name
   would be nice, but the GraphQL response only returns the ID, not the
   skill's display name — might need to maintain a custom mapping table, or
   have the user manually map skill names from the Alexa app).
4. **Safety net:** Confirmation before every deletion (show the list, user
   selects / user confirms "delete all devices from skill X"). No automatic
   mass deletion without explicit user confirmation — the API offers no
   undo.
5. **Region detection:** On first launch, iterate through the host list
   (above) and see which one correctly answers the public JSON endpoint
   (rather than redirecting to the login page).

## Known risks / limitations

- Undocumented, internal Amazon API — not supported by Amazon, can be
  changed/removed at any time without notice.
- No official rate limiting known, but presumably present — for very many
  devices, requests may need to be throttled/delayed.
- DELETE doesn't provide a reliable success confirmation in the response
  itself.
- Cookie-based auth means: the session can expire, the app may need to
  trigger a re-login periodically (show the WKWebView again).
