# Places list
**What this shows:** rows with an Open button that opens each place in OpenStreetMap, built from latitude and longitude. There is no map widget
**Edit these files:** `scripts/config.json` (`views[0].item.url` and `fields`) and `scripts/fixtures.json` (`places` with `lat` and `lon`).
**Run these commands** from the repo root (once before the first pack: `node toolkit/bin/bolt-apps.mjs keygen`; a higher `--version` each pack):
```
node toolkit/bin/bolt-apps.mjs lint kit/examples/places-list --personal
node toolkit/bin/bolt-apps.mjs check kit/examples/places-list
node toolkit/bin/bolt-apps.mjs pack kit/examples/places-list --personal --version 1.0.1 --out ../places-list-1.0.1.boltpack
node toolkit/bin/bolt-apps.mjs verify ../places-list-1.0.1.boltpack
```

## Notes
A personal app cannot draw a map: the launcher refuses the `map` pane kind for a personal app (see ENGINE.md). The link opens the system browser, https only. Swap the `url` template for any maps site.

Sample data is invented. The app calls `https://api.example.com`, which does not exist: point `api.base_url` and `endpoints[].path` at your own API, or keep using fixture mode in `check.json`. See `../ENGINE.md` for every option.

After editing `config.json`, rebuild the app file: `python3 scripts/engine.py --emit-yaml > utilities/places-list.yaml`. Drop the `.boltpack` on the Bolt launcher or Bolt Apps; the key never goes in the pack (see ENGINE.md, "Where to store keys").
