# script-template

## What this shows
A working script app on the kit that doubles as a tour of what a Bolt 181 app can draw, against a real free API with no key: the Art Institute of Chicago's public-domain artworks (`api.artic.edu` for the data, `www.artic.edu` for the pictures). Shipped as it is, it shows real data on the first run. Copy it to start your own: the structure stays, you swap the API and the fields.

What to see (type `=my-tool` after `new` and `ship`; the word `landscape` is the default search):
1. Overview: four number tiles. Public domain share with a meter and a CC0 badge; the peak period with a sparkline, a delta and a PEAK badge; the top department with a meter; how many pictures. Each tile drills (Enter).
2. List: `=my-tool items monet` (any word, two words work). A small picture (40 pixel avatar), facts, a markdown note and Open source and Copy summary buttons in the preview pane for the selected artwork; a tile for its period; one icon and badge per department and century.
3. Pictures: Enter on the Pictured tile (or `=my-tool pictures cats`): a grid of cards with the artworks' pictures.
4. Chart and table: Enter on the Peak period tile (a bar chart of artworks per period) and on the Top department tile (a table sorted by artworks, with a total).
5. Detail: Enter on an artwork for a markdown pane with a big picture (about 400 pixels wide, in proportion), the title, the artist and date, a short facts list, the description, credit, size, attribution and the Open source and Copy summary buttons; a Back row, a Back row and a raw record tree (Record (JSON)).

More: `kit/examples/SHOWCASE-script-template.md` in the repository has the exact commands and the expected result of each step, for recording.

## Edit these files
- `scripts/script-template__config.json`: change this first: the API (`api.base_url`, `hosts`, which must name EVERY host the script contacts, the picture host too), the endpoints (`path`, `data` key, `fields` asked for, `search_fields`, `periods`), the `fields` map from your API's names to this app's, the labels.
- `scripts/script-template__app.py`: `n_item()`, `n_items()` and `n_facets()` (read your API's answer; raise ValueError for an answer you cannot trust), `search_params()` (the query), `hero_row()`, `art_row()` and `build()` (rows; `md_escape()` for any API text that enters a markdown body), `emit_yaml()` (panes), `http_bytes()` (headers if your API wants one).
- `scripts/script-template__fixtures.json`: recorded answers (`search`, `facets`, `details`, `thumbs`, `heroes`). The ones here were recorded from the live API on 2026-11-17. Record your own: run once live and save what your API answered.
- `check.json`: the cases.

## Run these commands
```
./bolt-apps new script-template my-tool --dir apps   # copies kit/examples/script-template
./bolt-apps run apps/my-tool items --sample
./bolt-apps check apps/my-tool
./bolt-apps ship apps/my-tool # needs-network (not run by the README test: it writes your key and the pack to ~/.bolt-apps)
```
Then drop the `.boltpack` that `ship` prints on Bolt and type `=<chip>`. Run `./bolt-apps keygen` once if `ship` says you have no key.

## How it behaves
- Ships live (`api.fixture_default: false`): `ship` says "Start mode: live. This app needs no key." With the network down it shows the offline row or an old copy (up to 24 hours) labelled on its first row. `check` runs it in sample mode (`"fixture": true`) and every sample view says so.
- The API: `GET /api/v1/artworks/search` with a `bool` query (all words must match in the title, artist or medium, public domain only) for the list, and one more call with the same words and `limit=0` that asks for counts (matches, public-domain matches, per period, per department). `GET /api/v1/artworks/<id>` for the detail. No key. About 60 requests a minute per address (its `x-ratelimit-limit` header, measured 2026-11-16 and 2026-11-17); results are cached 10 minutes. Metadata is CC0; the description text is CC BY 4.0; images of public-domain works are CC0 (terms: https://www.artic.edu/terms). Every artwork row says so.
- What the numbers mean: "matches" are artworks whose title, artist or medium contains ALL the typed words (a `bool` query with operator and), so `landscape` gives 1,861 and 1,109 of them are public domain (re-checked live 2026-11-17 with that same query). A plain `q=landscape` search is a relevance search that returns the whole collection (133,287), so its totals differ. The tiles, chart and table count public-domain matches only.
- Errors: a connection failure shows "Could not reach ..." with OFFLINE; an HTTP 4xx from the API shows "did not accept that search"; a 429 shows "is busy". Words with `..`, `/` or `\` are refused before any request ("Type a word or two").
- Safety: https only, port 443, to the two hosts in `config.json`; redirects only on the host asked; no cookies or credentials; 8 s per API call (5 s per picture, 8 s for all pictures together); 1 MB cap per API answer; a picture is read only if it starts with the JPEG bytes and fits the cap; the typed word is only percent-encoded into the query; the picture host id is checked against the exact id shape before it enters a URL; every string goes through `kit.clean_text`; everything a person can paste (Enter on a detail row, Copy summary) goes through `kit.safe_copy` (a bullet first, no shell characters, bounded). The picture host refuses a user agent that is a bare library name or carries a web address, so `api.user_agent` is a plain name.
- Pictures (read from the launcher source, not seen in a running Bolt): a personal app pane never loads a web address, and the launcher's Content Security Policy allows only `data:` images. So the script fetches a JPEG and puts it in the row as `data:image/jpeg;base64,...`. A row text field is cut at 4,000 characters, so the picture is split over fields and the app file joins them in the template. Two sizes: the big picture of the detail pane (`images.hero` in `config.json`: 400 pixels wide, then 250, 220, 180 or 140 when the first is over 70,000 bytes, joined from `img1` to `img24`, up to about 94,000 characters; only the detail row carries it, fetched for that one artwork) and the small one of the `pictures` card grid (140 pixels wide, or 110 or 80, `img1` to `img4`, about 12 KB). The big picture is a markdown image in a markdown pane (`![]({{row.img1}}...{{row.img24}})`); Bolt shows an inline `data:` image in a markdown pane at its own size, shrunk to the pane width with its proportions kept (read from the pane source and a browser measurement of the same CSS, not seen in a running Bolt). The `entity_preview` pane would draw the same picture as a 40 pixel avatar by design of that pane, which is why the detail uses the markdown pane and the list keeps the entity preview with its tile. The picture host only serves 400 and 843 pixels wide and any width up to 250; a tall picture that is over the byte cap is fetched at a smaller width. Every string from the API that goes into the markdown body is escaped (`md_escape()`), so a title with brackets, a link or html shows as plain text. Pictures are cached 30 days; one that cannot be fetched is skipped for 15 minutes and its pane shows the text with a note.
- Panes drawn from the whole list (tiles, cards, chart, table) have no Back row in this app: press Esc or Left. Panes drawn per selected row (list, detail, record) start with a Back row whose pane is a short note.
- Rows go through the kit (`kit.row`, `kit.safe_row`, `kit.tile`, `kit.back_row`, `kit.note_row`, `kit.refresh_row`), so text is cleaned and the row contract is checked; a bad icon name raises a KitError that `run` and `check` print in full.
- The script reads its own folder first, so `python3 -I` works, and it writes no `__pycache__`.
- This is a personal app: it runs as you with your permissions. Only install code you have read.

## Making it your API
Keep the shape and change the data: `hosts` and `api.base_url`, then the endpoints and `fields`, then `n_item()`, `n_facets()` and `search_params()`. If your API needs a key, see `../feed-template` (key from the keychain or `~/.config/<id>/.env`, stripped from answers before they are cached). If it has no pictures, delete the `img*` fields, `attach_thumbs()`, `attach_heroes()` and the `pictures` view in `emit_yaml()`.

## Not covered
Pagination, parallel sources (see `../repo-radar` and `../around`), Windows. Not verified in real Bolt: the live runs, sample runs and shape checks pass here, but nothing ran in the launcher, so how the tiles (meter, sparkline, delta), the big picture pane, the card grid, the chart and the table look, and whether a Back-less grid view is comfortable, are read from the launcher source only.
