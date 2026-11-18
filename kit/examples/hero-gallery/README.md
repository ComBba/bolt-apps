# Hero gallery
**What this shows:** the `entity_preview` `hero` key (Bolt 182 and later): a list of pictures whose preview pane draws the selected picture full width at the top, with a caption pill and a credit line, then the title and text. The script draws three small PNGs itself and sends them as inline data. No network.
**Needs Bolt 182.** A Bolt 0.1.181 refuses a whole pack that uses `hero` (`unknown key for a entity_preview pane`), so `bolt-app.json` says `"min_bolt_version": "0.1.182"` and the pack must go only to people on Bolt 182 or newer. `lint`, `check` and `pack` fail without it.
**Edit these files:** `scripts/hero-gallery__config.json` (the pictures and the credit) and `scripts/hero-gallery__app.py` (`draw`, `picture_row`, `build`, `emit_yaml`).
**Run these commands** from the repo root (once before the first pack: `./bolt-apps keygen`; a higher `--version` each pack):
```
./bolt-apps lint kit/examples/hero-gallery --personal
./bolt-apps check kit/examples/hero-gallery
./bolt-apps pack kit/examples/hero-gallery --personal --version 1.0.0 --out ../hero-gallery-1.0.0.boltpack
./bolt-apps verify ../hero-gallery-1.0.0.boltpack
```

## Notes
- A row text field is cut at 4,000 characters, so `kit.hero_fields()` splits the picture over `img1`, `img2`, ... and the app file joins them: `src: "{{row.img1}}{{row.img2}}..."` (`kit.hero_src_template(n)` writes it). At most 16 parts, about 47 KB of picture, at most 1 MiB. The first picture is grainy on purpose so it takes about 12 parts.
- The standard library cannot resize a picture: give the kit one that is already small. A picture that needs more than 16 parts is refused with a KitError; the script then sends the row without the picture fields, and the pane shows no hero (the "No picture" row shows that).
- After changing `config.json`, rebuild the app file: `python3 scripts/hero-gallery__app.py --emit-yaml > utilities/hero-gallery.yaml` (run it from the app folder), then `./bolt-apps check kit/examples/hero-gallery --update-golden`.
- `image_url` stays a 40 pixel avatar; use `hero` for a large picture.
- Not verified in a running Bolt 182, and not tried on a 181 (which should refuse the pack): written from the Bolt 182 source and the row contract.
