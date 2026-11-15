# file-insights-template

## What this teaches
A local-file app: the person types the path of a CSV, the app reads it with the standard library only, finds the date, value and group columns by name, and shows totals, a titled line chart, a titled bar chart, a table and a list of things to watch. It is the file archetype: no network, `files` permission, read-only.

| View | Pane | What it shows |
|---|---|---|
| overview | cards (tiles) | verdict, row count, total, one row per insight rule |
| trend | chart, line | total per period (day, or month when there are over 40 days) |
| breakdown | chart, bar | total per group, top 10 |
| rows | table with a Total line | the first 25 usable rows |
| problems | markdown | skipped rows, bad dates, uneven rows, every cap that cut the file |

## How it behaves (measured by the check cases and by hand, 2026-11-15)
- `=insights ~/data/sales.csv`, or `=insights` alone for labelled sample data (a SAMPLE badge row, invented numbers). Up to four words are joined into one path, so a path with a few spaces works. A path whose first word is a view name (`trend`, `rows`) needs `./` in front.
- The last good path is kept for an hour (the kit cache, `~/.bolt-apps/cache/file-insights-template`) so the Trend, Breakdown, Rows and Problems rows reopen the same file. A launcher row can carry only a plain word, never a path, so the path cannot travel in the row.
- Caps (config `limits`): 5 MB read, 5,000 rows, 40 columns, 200 characters a cell. Each cap that cut the file is listed in Problems, never silent.
- Only a regular file is opened. A folder, pipe or device gets one plain row. A binary file (NUL bytes) is refused. A missing file says so.
- A cell that is empty or not a number is skipped and counted, never turned into 0. `nan` and `inf` are not numbers. Currency signs, thousands commas, `(40.00)` negatives and `12%` are read.
- Cell text is cleaned by the kit before display (bidi marks, zero-width characters, control characters, `{{`). A cell such as `=HYPERLINK(...)` is shown as text and never run. Nothing is written to your file.
- The newest period can be partial, so a drop in "Latest period" may only mean the month is not over.
- Not covered: Excel files, files over 5 MB (the first 5 MB is read and Problems says so), other text encodings than UTF-8.

## Copy this to build
Any app that reads one local file and explains it: a log summary, an expense export, a metrics dump. Change the columns and the rules, keep the reader.

## Edit only these fields
`scripts/file-insights-template__config.json`:
- `columns`: header words that mean date, value and group (case-insensitive). `mapping` pins an exact header, for example `{"value": "Net sales"}`.
- `date_formats`, `currency`, `unit`, `delimiters`, `limits`.
- `rules`: `sum`, `change` (`watch_below_pct`, `good_above_pct`), `top_share` (`watch_above_pct`), `outliers` (`z`), `missing` (`watch_above_pct`). Each has a `title` and `subtitle` template. Delete a rule to drop it.
- `charts`: the chart titles and types (`line`, `bar` or `sparkline` only). `table_columns`: the table.

`scripts/file-insights-template__fixtures.json`: the sample CSV (invented) and the demo files the tests use.

## Commands
Run `node toolkit/bin/bolt-apps.mjs keygen` once before the first pack: it makes your signing key and never overwrites one.
```
node toolkit/bin/bolt-apps.mjs kit vendor --flat kit/examples/file-insights-template
python3 kit/examples/file-insights-template/scripts/file-insights-template__insights.py --emit-yaml > kit/examples/file-insights-template/utilities/insights.yaml
node toolkit/bin/bolt-apps.mjs check kit/examples/file-insights-template --update-golden
node toolkit/bin/bolt-apps.mjs lint kit/examples/file-insights-template --personal
node toolkit/bin/bolt-apps.mjs pack kit/examples/file-insights-template --personal --version 1.0.1 --out file-insights-template-1.0.1.boltpack
```
Try the edge cases without a file: `=insights rows demo-hostile`, `=insights problems demo-ragged`, `demo-nonnumeric`, `demo-novalue`, `demo-empty`, `demo-huge`.
