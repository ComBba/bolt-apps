# Quick path: build a Bolt App

Read this page only. It is the one place for the rules. Every command is `./bolt-apps <command>`, run from the root of the clone (a short launcher for `toolkit/bin/bolt-apps.mjs`). Nothing here is verified in real Bolt yet; Windows is unproven; there is no sandbox (a personal script runs as you). Need more: [CAPABILITIES.md](CAPABILITIES.md) (what works, one snippet each), [ENGINE.md](ENGINE.md) (every config option).

## 1. Pick the template

| You need | Start from | Edit only | Read |
|---|---|---|---|
| A web API with a key: tiles, drill down, detail pane | `portal-template` | `scripts/config.json`, `scripts/fixtures.json` | `acme-dash` |
| Charts over rows | `chart-template` | same two | `widget-gallery` |
| A sortable table with totals | `table-template` | same two | `widget-gallery` |
| One word in, one card out | `lookup-template` | same two | itself |
| A typed form that saves rows | `form-template` | `scripts/config.json` | itself |
| A local file the person names | `file-insights-template` | `scripts/config.json`, `scripts/fixtures.json` | itself |
| One command line tool | `cli-wrapper-template` | `scripts/config.json`, `scripts/wrap.py` | itself |
| Quick local probes as tiles | `system-glance` | `scripts/system-glance.py` | itself |
| Several APIs joined | `repo-radar`, `around` | `scripts/config.json`, `scripts/fixtures.json`, the one script | itself |
| A service on this computer | `local-service-template` | `utilities/localmodels.yaml` | itself |
| An API no engine template fits | `script-template` | `scripts/config.json`, `scripts/fixtures.json`, `scripts/app.py` | itself |
| Reshape pasted text, no script | `./bolt-apps new <id> --type transform` | its yaml | [AGENTS.md](../../AGENTS.md) |

The edit lists are `edit` in [index.json](index.json). Examples live in `kit/examples/<template>`.

## 2. Four commands

Needs Node 18+ and Python 3.9+:

```sh run
./bolt-apps new portal-template my-tool --dir ~/my-apps    # copy, rename, make the sample pass
./bolt-apps run ~/my-apps/my-tool --sample                 # see the rows Bolt would show
./bolt-apps check ~/my-apps/my-tool                        # run its test cases
./bolt-apps ship ~/my-apps/my-tool                         # lint, check, pack, verify; prints the .boltpack
```

Edit between `new` and `run`. After editing an engine app's `scripts/config.json`, regenerate its app file: `cd ~/my-apps/my-tool && python3 scripts/engine.py --emit-yaml > utilities/my-tool.yaml`. Then drop the `.boltpack` on the Bolt launcher (never Admin settings), read the prompt, approve it, type `=mytool`. `ship` raises the version each time and keeps one signing key in `~/.bolt-apps`. Stuck: `./bolt-apps doctor ~/my-apps/my-tool`.

## 3. Ten hard rules

1. Edit only the files in the table. Never edit `engine.py`, `bolt_app_kit.py`, the lock file or a generated `utilities/<id>.yaml`.
2. `id` is lowercase letters, digits and hyphens, and equals the folder name.
3. Keys never go in a file, a pack, a row or an error (the kit hides them from API answers within the limits in the table). Use the keychain or `~/.config/<id>/.env` (mode 600). A shell variable does not reach the script under Bolt.
4. Ship live: `api.fixture_default` is `false`. Tests use sample data: `"fixture": true` at the top of `check.json`.
5. Use only the panes in the table below. Chart types are `line`, `bar` and `sparkline`. Others (pie, donut, area, heatmap, gauge) are not shipped.
6. Icon names are case-sensitive and come from `kit/schema/icons.json` (footer-button icons from a shorter lowercase list).
7. A nav arg is one plain token: no slash. Drill with `nav` (one Enter). A chain action (`kind: utility` with `target_chip`) only pre-fills the next command, so never use it to drill. A row's `pane` works when it names a view whose right pane has mode `selected_row` and kind entity_preview, detail, markdown, json_tree, chart, table or card; it is ignored for mode `list_data`, a view with no right pane, or kind diff, cards or image_grid.
8. A script app is tier 3: personal pack only, never the gallery. It runs as you. Install only code you have read.
9. A list shows at most 50 rows; a failed call is never shown as zero; an old copy shows its age.
10. Say what you did not verify. Today that is everything in real Bolt.

## 4. The rules table

| Limit | Bolt | Kit or engine |
|---|---|---|
| Views per app, overview included | 8 | 8 (7 plus the overview) |
| Footer buttons | 6 | 3 (Open and Copy count) |
| Footer label | 40 kept, 14 shown | write 14 or fewer |
| Rows in a list | 2000 | 200 in the row schema, 50 from the engine |
| Script timeout | 1 to 60 s, default 10 | engine requests 10 s each, 14 s together |
| Pane kinds with app data | card, markdown, entity_preview, chart, table, cards, detail, json_tree, diff, image_grid | same |
| Panes that cannot show app data | map, image, color, weather, date, calc | do not use |
| Footer action kinds | url, composer, utility, run | same |
| App file `schema_version` | 1 or 2 (2 makes pane bind mistakes errors) | 1 |
| Listing `bolt-app.json` `schema_version` | 1 | 1 |
| Environment a script sees | HOME, PATH, USER, LOGNAME, LANG, TERM, TMPDIR, TZ, LC_*, XDG_*, SSL_CERT_FILE, SSL_CERT_DIR, REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE, NODE_EXTRA_CA_CERTS; Bolt sets PYTHONNOUSERSITE, PYTHONDONTWRITEBYTECODE, PYTHONUNBUFFERED | no names containing TOKEN, KEY, SECRET, PASS, PWD, CRED, AUTH, PRIVATE, SESSION, COOKIE |
| Keys in API answers | Bolt does not scan them | the kit removes the key (as written, URL-encoded, hex, base64, any letter case), `user:password@` in addresses and credential-named query values (`token`, `api_key`, `sig`, `secret`...) from an answer before it is cached or shown |
| What the kit cannot hide | | HTTP Basic base64 at another alignment, HTML entities, colon-separated hex, a key split across lines, a key held as a JSON number, a value URL-encoded twice; a key under 3 characters is refused |
| Sandbox | not shipped | not shipped |

The same numbers live in `schema/bolt-rules.json`; a test keeps this table equal to it.

## 5. When Bolt says no (Bolt 0.1.181)

| Bolt says or does | Do this |
|---|---|
| After a drop the dialog says `Installed ... Ready to use: your-app-id` | Type `=<chip>`. 181 refreshes its list after a pack install. A file you saved into the User Apps folder by hand needs Reload. |
| The chip is missing | Settings, Desktop App, User Apps, click Reload. A file that failed to load is listed there with the reason. |
| "Not run. Needs your OK" | Press Enter on the app's run row, read what it can do, accept. First run only. |
| HIGH RISK in the install prompt | Normal for a personal app that runs a script (tier 3). Read the permissions, confirm only code you have read. |
| "a pack is only replaced by a newer version" | `ship` already raises the version. If you packed by hand, pass a higher `--version`. To go back, remove the app first (see the Remove row). |
| "already belongs to" another signer | Pack with the key you first used (`~/.bolt-apps/key.pem`), or remove the installed app (see the Remove row) and ship again. |
| "Bundle rejected" | You dropped it in Admin settings. Drop it on the Bolt launcher or Bolt Apps. |
| Remove | Remove the app in Settings, Desktop, User Apps (the Remove button is on the app's row in 181 (not yet seen on a running 181 build); newer builds also show it in the expanded panel next to Revoke approval). Do not delete files by hand: Bolt keeps an install record, and a hand-deleted file can leave `owned_by_other` behind. Remove deletes the app's YAML and, for a pack's last app, its scripts and install record. If you cannot find a Remove button on your build, tell us which Bolt version you have. If you built apps before a fix was announced for them: remove the app this way, then `./bolt-apps ship` it again. |

Written from the 0.1.181 source, not seen in a running 181. Anything that needs a newer Bolt is marked "newer than 181" where it appears; none is promised here (for example, an install that needs no Reload even for hand-saved files, or an in-place Remove confirmation, are newer than 181).

## 6. Where things stand

Sample mode: `run --sample` and `check` need no key and no network. Live mode: put the key in the keychain or the `.env` file, then `run --live`. Not shipped: confinement of scripts, native MCP (a script can call one tool over stdio, tested only against a stand-in), Windows runs. The `permissions` block in an app file is shown at install and not enforced.
