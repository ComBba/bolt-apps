# acme-dash

The public example built from `../portal-template`: a fictional Acme Co compliance dashboard. Type `=acme-dash`.

- Overview: readiness 82%, tasks 41 of 50, policies, controls, risks, vendors, devices, people, trust portal.
- Drill down: overview, then a list, then (for controls) a detail view with the linked tasks. Back is always the first row.
- `=acme-dash tasks urgent` filters the task list by one word.
- Ships live: with no key it shows labelled sample data (`api.on_missing_key` is `sample`), so a first run is never an error. `check` runs it on the sample data in `scripts/acme-dash__fixtures.json` (`"fixture": true` in `check.json`), so tests need no key and no network. Put `ACME_API_KEY=...` in `~/.config/acme-dash/.env` (`chmod 600`) for the real API. To demo it on sample data in your own copy, set `api.fixture_default` to `true`.

All people, companies and numbers are made up. The only code is `scripts/acme-dash__engine.py`, identical to the template's; this folder differs only in `config.json` and `fixtures.json`.

Permissions in words: it runs a script on your computer, can reach the API host in `config.json`, and reads the `.env` file named there.

Pack it for yourself, from inside this folder:

```
bolt-apps lint . --personal
bolt-apps pack . --personal --version 1.0.1 --out ../acme-dash-1.0.1.boltpack
```

- Raise the version every time: Bolt refuses a pack whose version is the same as, or older than, the one installed (`same_or_older_version`). Build with `pack --personal --version X --out ../<id>-<ver>.boltpack`, and keep the pack outside the folder.
- Key storage: the system keychain, or `~/.config/<app id>/.env` (`chmod 600`). A key exported in your shell never reaches the script when Bolt runs it; see `../ENGINE.md`.

Run `./bolt-apps keygen` once before the first pack: it makes your signing key and never overwrites one.
