# Unit convert
**What this shows:** a typed input form (a number and two selects) that answers with a result row and a detail pane (result, formula, reverse, kind), plus the same amount in the other units. No network.
**Edit these files:** `scripts/config.json` (the unit table, defaults, temperature formulas) and `scripts/app.py` (`convert`, `build`, `emit_yaml`).
**Run these commands** from the repo root (once before the first pack: `./bolt-apps keygen`; a higher `--version` each pack):
```
./bolt-apps lint kit/examples/unit-convert --personal
./bolt-apps check kit/examples/unit-convert
./bolt-apps pack kit/examples/unit-convert --personal --version 1.0.1 --out ../unit-convert-1.0.1.boltpack
./bolt-apps verify ../unit-convert-1.0.1.boltpack
```

## Notes
- The launcher shows the form from the `inputs:` block of the app file and passes each value to the script as a word, in order. The script checks the words again: a number, two units from the table, and the same kind. A bad value gives one plain row and nothing else.
- Adding a unit: put it in `config.json` under its kind with its size in the base unit (metre, kilogram), then rebuild the app file: `python3 scripts/app.py --emit-yaml > utilities/unit-convert.yaml`. A new kind with a non-linear formula needs a code branch like `temperature`.
- Six significant digits are shown, without an exponent between 1e-15 and 1e15 (outside that, `1.23457e+21`). An amount above 1e15, a result above 1e30 and a temperature below absolute zero give a plain refusal row.
- The Copy button puts the result line in the composer.
- It makes no network call, so there is no fixture file and `check.json` has no `fixture` flag.
- Not verified in real Bolt: the form and the detail pane were checked against the row contract only.

