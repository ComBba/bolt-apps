# Sky Watch
**What this shows:** several keyless public sources in one app: where the ISS is (`api.wheretheiss.at`), the next launches (`ll.thespacedevs.com`, rate limited, cached 10 minutes), earthquakes M4.5 and up in the last day (`earthquake.usgs.gov`) and, when you type a city, weather and sunrise and sunset (`geocoding-api.open-meteo.com`, `api.open-meteo.com`). Every row has one preview pane (SOURCE, WHEN, KEY FIGURE, DATA) with Open source and Copy summary.
**Edit these files:** `scripts/sky-watch__config.json` (hosts, sources, TTLs, limits) and `scripts/sky-watch__fixtures.json` (recorded answers used by `check` and `demo`).
**Run these commands** from the repo root (once before the first pack: `node toolkit/bin/bolt-apps.mjs keygen`; a higher `--version` each pack):
```
node toolkit/bin/bolt-apps.mjs lint kit/examples/sky-watch --personal
node toolkit/bin/bolt-apps.mjs check kit/examples/sky-watch
node toolkit/bin/bolt-apps.mjs pack kit/examples/sky-watch --personal --version 1.0.1 --out ../sky-watch-1.0.1.boltpack
node toolkit/bin/bolt-apps.mjs verify ../sky-watch-1.0.1.boltpack
```

## Notes
- Type `=sky-watch` for the sky now, `=sky-watch launches`, `=sky-watch quakes`, `=sky-watch Paris` (any first word that is not a view is a city, up to four words), `=sky-watch demo` for labelled recorded answers (no network).
- Safety: https only, to the five hosts in `config.json`; redirects only on the same host; no cookies or credentials; 8 s per request and 14 s in all; a 1 MB cap per answer; typed text is only percent-encoded into the query; every string is cleaned by the kit. A failed source shows an old copy (up to 24 h) when there is one, else one offline row.
- The app-level right pane is the same preview as every view, so a typed city is drawn safely too.
- Sample data is recorded and invented (`example` places, labelled SAMPLE DATA with `demo`). Not verified in real Bolt: the live runs, the preview pane and the Open source link were checked against the row contract and the check rules only.
After editing `config.json`, rebuild the app file: `python3 scripts/sky-watch__sky-watch.py --emit-yaml > utilities/sky-watch.yaml`.
