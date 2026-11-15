# lookup-template

## What this teaches
One typed word in, a stitched result out. Two chained keyless calls (Open-Meteo geocoding, then the forecast for the first match), laid out as tiles with a 24 hour sparkline, three day rows, and Open in Maps and Open forecast links. This is the lookup archetype: `mode: lookup` with `steps`.

## Live terms, checked 2026-11-15 with real requests
- Geocoding `geocoding-api.open-meteo.com/v1/search` and forecast `api.open-meteo.com/v1/forecast`: no key, HTTPS, JSON. The forecast answers with `X-RateLimit-Limit: 600` per 60 seconds. Free for non-commercial use; credit Open-Meteo (CC BY 4.0). A `User-Agent` is sent (`api.user_agent`).
- The app caches each call (`cache.ttl` 900 s) and falls back to an old copy up to a day when the API fails.

## What a personal app cannot do here (built-in `=weather` can)
The themed sky card, the C/F toggle and the icon-only action bar. The `weather` pane kind does not show app data (Bolt says so), so this app uses tiles instead. Typing more than three words is cut off (three query words are passed).

## Copy this to build
Any "type a name, see a card" lookup over one or two APIs.

## Edit only these fields
`scripts/config.json`: `endpoints` (a path may use `{query}` and `{earlier_step.field}`), `lookup.steps`, `lookup.rows` (templates over the results, dotted paths and list indexes allowed, `trend_path` for a sparkline), `maps` (value labels such as weather codes). `scripts/fixtures.json`: the two recorded responses (real, trimmed). Details: `../ENGINE.md`.

## Commands
Run `node toolkit/bin/bolt-apps.mjs keygen` once before the first pack: it makes your signing key and never overwrites one.
```
node toolkit/bin/bolt-apps.mjs kit vendor --flat kit/examples/lookup-template
python3 kit/examples/lookup-template/scripts/engine.py --emit-yaml > kit/examples/lookup-template/utilities/lookup-template.yaml
node toolkit/bin/bolt-apps.mjs check kit/examples/lookup-template --update-golden
node toolkit/bin/bolt-apps.mjs lint kit/examples/lookup-template --personal
node toolkit/bin/bolt-apps.mjs pack kit/examples/lookup-template --personal --version 1.0.1 --out lookup-template-1.0.1.boltpack
```
Live is the default. `check` runs sample mode through `"fixture": true` in `check.json`.
