# table-template

## What this teaches
The `table` pane: columns with `label`, `align`, `format` (text, number, percent, currency, date), `unit`, per-column `total` (sum, avg, min, max, count), `sort` and `totals_label`. A share column stands in for a pie chart, which the launcher cannot draw. `app.searchable: true` lets the launcher filter rows as you type.

## Copy this to build
Any list that needs sorting and totals: orders, invoices, usage, inventory.

## Edit only these fields
`scripts/config.json`: `endpoints`, `views[].item.extra` (one field per column; numbers stay numbers when the value is exactly `{field}`), `widget.bind.columns`. `scripts/fixtures.json`. Details: `../ENGINE.md`.

## Behaviour
A table shows every row, so the data view has no Back or refresh rows. The pane can draw 500 rows, but the engine hands a view at most 50 (`MAX_ROWS` in `engine.py`), and the view says "showing the first 50". A stale or partial notice appears as one extra row only when the data could not be refreshed.

## Commands
Run `node toolkit/bin/bolt-apps.mjs keygen` once before the first pack: it makes your signing key and never overwrites one.
```
node toolkit/bin/bolt-apps.mjs kit vendor --flat kit/examples/table-template
python3 kit/examples/table-template/scripts/engine.py --emit-yaml > kit/examples/table-template/utilities/table-template.yaml
node toolkit/bin/bolt-apps.mjs check kit/examples/table-template --update-golden
node toolkit/bin/bolt-apps.mjs lint kit/examples/table-template --personal
node toolkit/bin/bolt-apps.mjs pack kit/examples/table-template --personal --version 1.0.1 --out table-template-1.0.1.boltpack
```
