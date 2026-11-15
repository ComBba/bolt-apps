# script-template

## What this shows
A blank script app on the kit, for an API or a tool no engine template fits. One list endpoint, three views (overview tiles, a list with a filter word, a detail with Back), a fresh cache and an old copy in code, an offline row, a setup row for a missing key, a key stripped from the API's answer before it is cached, sample mode, and `--emit-yaml` so the app file is generated from `config.json`.

## Edit these files
- `scripts/config.json`: id, chip, title, the API (`base_url`, `hosts`, `key_env`, `auth_in`/`auth_param`), the endpoint path and `data` key, the field names, badges and tile labels.
- `scripts/app.py`: `n_items()` (read your API's answer; raise ValueError for an answer you cannot trust), `http_get()` (headers if your API wants one), `build()` and `emit_yaml()` (rows and panes).
- `scripts/fixtures.json`: a recorded answer from your API (the one here is invented, labelled SAMPLE DATA).
- `check.json`: the cases. Keep the one that proves an echoed key never reaches the cache (`home_absent`).

## Run these commands
```
node toolkit/bin/bolt-apps.mjs new script-template my-tool --dir apps   # copies kit/examples/script-template
node toolkit/bin/bolt-apps.mjs run apps/my-tool items --sample
node toolkit/bin/bolt-apps.mjs check apps/my-tool
node toolkit/bin/bolt-apps.mjs ship apps/my-tool # needs-network (not run by the README test: it writes your key and the pack to ~/.bolt-apps)
```
Then drop the `.boltpack` that `ship` prints on Bolt and type `=<chip>`. Run `node toolkit/bin/bolt-apps.mjs keygen` once if `ship` says you have no key.

## How it behaves
- Ships live (`api.fixture_default: false`): with no key it shows the exact one-line setup; with the network down it shows the offline row or an old copy with its age. `check` runs it in sample mode (`"fixture": true`).
- Keys: keychain, then `~/.config/<id>/.env` (mode 600), read with `kit.get_secret`; a shell variable reaches the script only in a terminal. The answer goes through `kit.redact_tree` before anything is cached or shown.
- Rows go through the kit (`kit.row`, `kit.safe_row`, `kit.tile`, `kit.back_row`, `kit.refresh_row`), so text is cleaned and the row contract is checked; a bad icon name raises a KitError that `run` and `check` print in full.
- The script reads its own folder first (`sys.path`), so `python3 -I` works, and it writes no `__pycache__`.
- This is a personal app: it runs as you with your permissions. Only install code you have read.

## Not covered
Pagination, per-id detail requests, parallel sources (see `../repo-radar` and `../around`), Windows.
