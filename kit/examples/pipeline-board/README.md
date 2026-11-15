# Pipeline board
**What this shows:** stages that drill into their runs, a detail pane with a meter per run, and a `diff` pane for what changed
**Edit these files:** `scripts/config.json` (`views`, `children`, the diff `bind`) and `scripts/fixtures.json` (`stages`, `runs`, `changes`).
**Run these commands** from the repo root (once before the first pack: `node toolkit/bin/bolt-apps.mjs keygen`; a higher `--version` each pack):
```
node toolkit/bin/bolt-apps.mjs lint kit/examples/pipeline-board --personal
node toolkit/bin/bolt-apps.mjs check kit/examples/pipeline-board
node toolkit/bin/bolt-apps.mjs pack kit/examples/pipeline-board --personal --version 1.0.1 --out ../pipeline-board-1.0.1.boltpack
node toolkit/bin/bolt-apps.mjs verify ../pipeline-board-1.0.1.boltpack
```

## Notes
The diff reads two multi-line fields. A field named `left`, `right` or ending in `_lines` keeps its line breaks, which is why `item.extra` uses `left` and `right`.

Sample data is invented. The app calls `https://api.example.com`, which does not exist: point `api.base_url` and `endpoints[].path` at your own API, or keep using fixture mode in `check.json`. See `../ENGINE.md` for every option.

After editing `config.json`, rebuild the app file: `python3 scripts/engine.py --emit-yaml > utilities/pipeline-board.yaml`. Drop the `.boltpack` on the Bolt launcher or Bolt Apps; the key never goes in the pack (see ENGINE.md, "Where to store keys").
