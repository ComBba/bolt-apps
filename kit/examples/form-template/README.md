# form-template

## What this teaches
A declarative input form (number, select, date, text with a length limit, toggle), checks on the values, a local log, and the log shown as a table.

## Copy this to build
Any app that takes a few typed values and shows what was recorded: expenses, time entries, bug reports, check-ins.

## Edit only these fields
`scripts/form-template__config.json`, section `form`: `inputs`, `submit.label`, `record` (what is saved), `item` (how a saved row shows), `widget.bind.columns`, `store.file`. `app` for the id, chip and title. Regenerate the app file and run check (see `../ENGINE.md`).

## How it behaves
- The launcher shows the form and passes each value as a word, in input order. The engine checks them again (required, number range, option list, date shape, length, pattern). A bad value shows one "Not saved" row and saves nothing.
- A valid submit appends one line to `store.file` (default `~/.bolt-apps/form-template/entries.jsonl`, folder `0700`, file `0600`, never through a link, newest 200 kept) and shows the log, newest first. Fixture mode adds the sample rows from `fixtures.json` below your own.
- Declared permissions: it runs a script and writes that one file. It makes no network calls.
- Not covered: sending the entry to a web API. Use the `views` mode for reading APIs.

## Commands
Run `./bolt-apps keygen` once before the first pack: it makes your signing key and never overwrites one.
See `../ENGINE.md`. Use a higher `--version` each time you pack again.
```
./bolt-apps lint kit/examples/form-template --personal
./bolt-apps check kit/examples/form-template
./bolt-apps pack kit/examples/form-template --personal --version 1.0.1 --out ../form-template-1.0.1.boltpack
```
