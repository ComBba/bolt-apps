# script-template

## What this shows
A working script app on the kit, against a real free API with no key: the Art Institute of Chicago's public-domain artworks (`api.artic.edu`, pictures from `www.artic.edu`). Shipped as it is, it shows real data on the first run. Views: overview (two number tiles and a featured artwork), `items` (a list with a search word, a preview pane per artwork: small picture, facts, attribution, Open source and Copy summary), `item` (one artwork with its description and Back), `pictures` (a grid of cards) and `grid` (a plain thumbnail grid). It also has a fresh cache and an old copy in code, an offline row, sample mode, and `--emit-yaml` so the app file is generated from `config.json`.

## Edit these files
- `scripts/script-template__config.json`: change this first: the API (`api.base_url`, `hosts`, which must name EVERY host the script contacts, the picture host too), the endpoints (`path`, `data` key, `fields` asked for), the `fields` map from your API's names to this app's, the labels.
- `scripts/script-template__app.py`: `n_item()` and `n_items()` (read your API's answer; raise ValueError for an answer you cannot trust), `art_row()` and `build()` (rows), `emit_yaml()` (panes), `http_bytes()` (headers if your API wants one).
- `scripts/script-template__fixtures.json`: recorded answers (`search`, `details`, `thumbs`). The ones here were recorded from the live API on 2026-11-16. Record your own: run once live and save what your API answered.
- `check.json`: the cases.

## Run these commands
```
./bolt-apps new script-template my-tool --dir apps   # copies kit/examples/script-template
./bolt-apps run apps/my-tool items --sample
./bolt-apps check apps/my-tool
./bolt-apps ship apps/my-tool # needs-network (not run by the README test: it writes your key and the pack to ~/.bolt-apps)
```
Then drop the `.boltpack` that `ship` prints on Bolt and type `=<chip>`. Run `./bolt-apps keygen` once if `ship` says you have no key. Try `=my-tool`, `=my-tool items hokusai`, `=my-tool pictures`, `=my-tool grid cats`, or any other word to search.

## How it behaves
- Ships live (`api.fixture_default: false`): `ship` says "Start mode: live. This app needs no key." With the network down it shows the offline row or an old copy (up to 24 hours) with its age. `check` runs it in sample mode (`"fixture": true`) and every sample view says so in a row.
- The API: `GET /api/v1/artworks/search?q=<word>` with `query[term][is_public_domain]=true`, 9 results, and `GET /api/v1/artworks/<id>` for the detail. No key. About 60 requests a minute per address (its `x-ratelimit-limit` header, measured 2026-11-16); results are cached 10 minutes. Metadata is CC0; the description text is CC BY 4.0; images of public-domain works are CC0 (terms: https://www.artic.edu/terms). Every artwork row says so.
- Safety: https only, port 443, to the two hosts in `config.json`; redirects only on the host asked; no cookies or credentials; 8 s per API call (5 s per picture, 8 s for all pictures together); 1 MB cap per API answer; a picture is read only if it starts with the JPEG bytes and fits the cap; the typed word is only percent-encoded into the query; the picture host id is checked against the exact id shape before it enters a URL; every string goes through `kit.clean_text`. The picture host refuses a user agent that is a bare library name or carries a web address, so `api.user_agent` is a plain name.
- Pictures (read from the launcher source, not seen in a running Bolt): a personal app pane never loads a web address, and the launcher's Content Security Policy allows only `data:` images. So the script fetches a small JPEG (140 pixels wide, or 110 or 80 if the first is too big for the fields) and puts it in the row as `data:image/jpeg;base64,...`. A row text field is cut at 4,000 characters, so the picture is split over `img1` to `img4` and the app file joins them (`{{row.img1}}{{row.img2}}{{row.img3}}{{row.img4}}`, about 12 KB of picture). The `entity_preview` pane draws it as a 40 pixel avatar (a User App cannot ask for a large one); `pictures` (cards) and `grid` (image_grid) draw it large. Thumbnails are cached 30 days; one that cannot be fetched is skipped for 15 minutes and its row shows without a picture.
- Rows go through the kit (`kit.row`, `kit.safe_row`, `kit.tile`, `kit.back_row`, `kit.refresh_row`), so text is cleaned and the row contract is checked; a bad icon name raises a KitError that `run` and `check` print in full.
- The script reads its own folder first, so `python3 -I` works, and it writes no `__pycache__`.
- This is a personal app: it runs as you with your permissions. Only install code you have read.

## Making it your API
Keep the shape and change the data: `hosts` and `api.base_url`, then the endpoints and `fields`, then `n_item()`. If your API needs a key, see `../feed-template` (key from the keychain or `~/.config/<id>/.env`, stripped from answers before they are cached). If it has no pictures, delete the `img*` fields, `attach_thumbs()` and the `pictures` and `grid` views in `emit_yaml()`.

## Not covered
Pagination, parallel sources (see `../repo-radar` and `../around`), Windows. Not verified in real Bolt: the live runs, sample runs and shape checks pass here, but nothing ran in the launcher, so how the preview avatar, the card grid and the thumbnail grid look, and that a click on a thumbnail does nothing useful, are read from the launcher source only.
