# FUSKY tracking bridge

FastAPI bridge for Garmin LiveTrack and the optional Find My fallback. It returns only the latest
latitude/longitude report to a browser that supplies the shared bearer token. Garmin mode reads a
public LiveTrack capability URL and needs no Garmin account credentials. The response includes the
latest position plus the session's travelled track, allowing the frontend to overlay it on the GPX.
Apple credentials,
account sessions and accessory keys stay in `backend/secrets/`, which Git ignores.

Both integrations are unofficial and can break when Garmin or Apple changes its services. This is
not a safety or emergency-tracking system.

## 1. Run safely in mock mode

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --env-file .env --host 0.0.0.0 --port 8000
```

Generate a token (it is your own shared secret, not something supplied by Apple or GitHub):

```bash
openssl rand -hex 32
```

Copy the result into `TRACKING_ACCESS_TOKEN` in `.env`, then test:

```bash
curl http://127.0.0.1:8000/health
curl -H "Authorization: Bearer YOUR_TOKEN" http://127.0.0.1:8000/api/location
```

Open the site's `/live/` page and enter `http://YOUR_MAC_LAN_IP:8000` plus the token. That works
when the site is also served over HTTP on the LAN. A public HTTPS GitHub Pages site requires an
HTTPS backend; browsers block requests from HTTPS pages to an HTTP backend.

## 2. Track Garmin LiveTrack

Leave `LOCATION_PROVIDER=mock`; the dedicated Garmin endpoint is available independently of the
fallback provider. Start a LiveTrack session, copy the session URL from Garmin Connect, then enter
that URL, the tracking API URL and `TRACKING_ACCESS_TOKEN` on the site's `/live/` page.
`GARMIN_DEVICE_NAME` controls the Garmin label independently from the `DEVICE_NAME` used by Find My.

The frontend calls `GET /api/garmin/location` with the session URL in the
`X-Garmin-LiveTrack-Url` header. The endpoint accepts only HTTPS session links on
`livetrack.garmin.com`, caches Garmin reads for `CACHE_SECONDS`, and returns the newest point. It
scrapes Garmin's public Next.js page because Garmin provides no supported consumer LiveTrack feed;
the parser may require maintenance if Garmin changes that page.

Test it directly:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Garmin-LiveTrack-Url: YOUR_GARMIN_SESSION_URL" \
  http://127.0.0.1:8000/api/garmin/location
```

## 3. Create the Apple login session

Do this interactively, never in a deployment or CI job:

```bash
cd backend
uv run python -m app.login
```

The script prompts for the Apple Account password and 2FA, then writes
`secrets/account.json` with owner-only file permissions. FindMy.py recommends reusing the saved
session rather than creating a new virtual device/login each time.

## 4. Export an official AirTag or iPhone

FindMy.py needs the official device's decryption state as `secrets/device.json`.

- macOS 14 or earlier: while logged into the same Apple Account and able to see the device in
  Find My, run `python3 -m findmy decrypt --out-dir devices/`. The command opens an interactive
  Keychain password prompt and does not work over SSH.
- macOS 15: first try the same command. FindMy.py documents a more invasive fallback using
  `beaconstorekey-extractor`; follow its upstream instructions carefully and restore SIP afterward.
- macOS 26: as of September 2026, upstream documents no working extraction method because the
  required BeaconStoreKey is protected. Do not disable SIP expecting that to fix it. Use a JSON
  exported previously or a trusted Mac running a supported version.

Copy the JSON for the intended device to `backend/secrets/device.json`. Never send or commit it:
it contains keys that can retrieve/decrypt that device's Find My reports.

## 5. Enable the Find My provider

Update `.env`:

```dotenv
APP_ENV=production
LOCATION_PROVIDER=findmy
TRACKING_ACCESS_TOKEN=generate-a-long-random-value-here
ALLOWED_ORIGINS=https://sebo-the-tramp.github.io
DEVICE_NAME=Sebastian
FINDMY_ACCOUNT_PATH=secrets/account.json
FINDMY_DEVICE_PATH=secrets/device.json
FINDMY_ANISETTE_PATH=secrets/ani_libs.bin
```

Then run the same `uvicorn` command. The service:

- requires the bearer token for `/api/location`;
- permits browser requests only from configured origins;
- caches upstream results for 30 seconds;
- marks old reports as stale;
- sets `Cache-Control: no-store`; and
- never serializes the Apple session, accessory state or report key to the browser.

## 6. Deployment

The included `Dockerfile` can run on a private server or container host. Mount `secrets/` as a
persistent private volume rather than copying it into an image. Terminate TLS in front of the
container, restrict inbound access, and back up the state securely. Do not put Apple credentials or
the crew bearer token in GitHub Pages variables prefixed with `PUBLIC_`; those values are bundled
into public JavaScript.

The frontend accepts the API URL and token interactively. Use **Create crew link** to generate a
capability URL in this format:

```text
http://YOUR_MAC_LAN_IP:4321/fusky-crew/live/#api=http%3A%2F%2FYOUR_MAC_LAN_IP%3A8000&token=YOUR_TOKEN
```

The recipient's page reads the URL fragment, removes it from the address bar, and connects
automatically. URL fragments are not sent to the web server or in HTTP referrer headers, but the
original URL still contains the bearer token and may remain in chat, clipboard, browser sync or
screenshots. Treat the link as a password. Anyone holding it can read the location; change
`TRACKING_ACCESS_TOKEN` and restart the backend to revoke all existing crew links.

The API URL is otherwise kept in `localStorage`; a manually entered token exists only in the
current tab's memory.

## Test

```bash
cd backend
uv run pytest
uv run ruff check app tests
```

## Tracking an iPhone

FindMy.py treats iPhones/iPads/Macs as official Find My devices and can query them if you have the
corresponding exported device JSON. This is report polling, not continuous GPS streaming: repeated
30-second requests may return the same older report. For race safety, keep official race tracking
and normal phone contact as the primary systems.
