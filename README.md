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

GitHub Pages is read-only. Live location therefore needs an external data source.

Recommended architecture:

Runner phone / tracker → Supabase table → static site reads latest point.

For race reliability, a dedicated tracker/app is better than browser geolocation because mobile browsers may suspend background updates.
