# system-glance

## What this teaches
The command-probe archetype on the flat kit: three read-only probes (`df`, `uptime`, `lsof` or `ss`) run in parallel inside one deadline, each parsed on its own. A probe that fails is shown as "not read" and never as zero or all clear. Per-OS command table, a 45 second cache for the disk probe, a Disk drill view, copy action.

## Notes
- The kit is the single file `scripts/system-glance__bolt_app_kit.py` (flat). The bridge command names it as `{{scripts_dir}}/system-glance__bolt_app_kit.py`, so Bolt includes it in what the person approves.
- `check.json` uses `fixtures/<os>/*.out` as stand-ins for the commands. The Linux and Windows cases are fixture-only: they were not run on those systems.
- For wrapping a command with typed arguments, validation and a titled chart, see `../cli-wrapper-template`.

## Commands
Run `./bolt-apps keygen` once before the first pack: it makes your signing key and never overwrites one.
```
./bolt-apps kit vendor --flat kit/examples/system-glance
./bolt-apps check kit/examples/system-glance
./bolt-apps lint kit/examples/system-glance --personal
./bolt-apps pack kit/examples/system-glance --personal --version 1.0.1 --out system-glance-1.0.1.boltpack
```
