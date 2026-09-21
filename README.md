# FUSKY 55K Crew Command

Mobile-first static crew website for FUSKY 55K.

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

GitHub Pages is read-only, so live location uses the separate protected FastAPI service in
`backend/`. The `/live/` page polls that service and displays the latest report with Leaflet.

Architecture:

Find My network → FindMy.py → authenticated FastAPI → Leaflet client

Start with [backend/README.md](backend/README.md). Never commit the Apple account session or
accessory JSON: both are ignored under `backend/secrets/`.

Find My updates are delayed reports, not continuous GPS. For race reliability and safety, keep the
official event tracker and direct phone contact as the primary systems.
