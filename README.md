# FUSKY 55K Crew Command

Mobile-first static crew website for FUSKY 55K - 2026

## Edit crew

Each person has one Markdown file:

`src/content/crew/<name>.md`

Front matter:

```yaml
---
name: Alex
role: film   # film | support | drink | drone | lead
phone: ""
color: "#ff5a36"
priority: 1
---
```

Everything below the front matter is that person's personal brief.

## Local development

```bash
npm install
npm run dev
```

## GitHub Pages

1. Push this repository to GitHub.
2. In GitHub: Settings → Pages → Source: GitHub Actions.
3. The included workflow builds and deploys the site. The account and repository
   path are detected automatically from `GITHUB_REPOSITORY`.

For a custom domain or path, set `SITE_URL` and `BASE_PATH` when building.

## Live location

The preferred race-day tracker is Garmin LiveTrack. Start LiveTrack on the Forerunner 965, copy
the active session URL from Garmin Connect, then paste it into `/live/` together with the protected
tracking API address and token. The backend reads the latest public session point and the frontend
plots it on the FUSKY course map. The page also creates a private crew link containing those three
values in its URL fragment.

The session URL is a capability link. Anyone who receives it can view the Garmin session, so share
the generated crew link privately. Standard LiveTrack is sufficient and does not require a Garmin
Connect+ subscription. A new standard LiveTrack URL is generated for each session. Garmin does not
permit the static site to read the feed directly, so the FastAPI service in `backend/` is required.
This integration reads Garmin's public page format rather than an official API and can break if
Garmin changes that format.

Find My remains available as an optional fallback through the same service.

Garmin architecture:

Forerunner → Garmin LiveTrack → authenticated FastAPI bridge → Leaflet client

Find My fallback:

Find My network → FindMy.py → authenticated FastAPI → Leaflet client

Start with [backend/README.md](backend/README.md). Never commit the Apple account session or
accessory JSON: both are ignored under `backend/secrets/`.

Find My updates are delayed reports, not continuous GPS. For race reliability and safety, keep the
official event tracker and direct phone contact as the primary systems.


```bash
uv run uvicorn app.main:app --env-file .env --host 0.0.0.0 --port 8000
```
