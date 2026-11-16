# The shared engine: every config option, once

> **Chip equals id:** the app file's `chip` must be the app's `id` (the launcher looks apps up by id, in Bolt 181 and main); `lint` refuses anything else as `chip_not_id`.

> **Apps built before this change:** remove the old app in Bolt (Settings, Desktop, User Apps; the Remove button is on the app's row on 181, and newer builds also show it in the expanded panel; do not delete files by hand), run `./bolt-apps new <template> <id>`, copy your own `config.json` and `fixtures.json` over the new ones, re-run `./bolt-apps check`, then `./bolt-apps ship`.

`bolt-apps` in this page means `./bolt-apps`, run from the root of the clone. Limits live in [the rules table](QUICKSTART.md#4-the-rules-table); what is supported is in [CAPABILITIES.md](CAPABILITIES.md).

All apps here run the same engine, kept as `scripts/<id>__engine.py` (every file in `scripts/` is named `<id>__<name>`). An app is `scripts/<id>__config.json` plus `scripts/<id>__fixtures.json`. Nothing else is edited. Regenerate the app file after any change:

```
python3 scripts/<id>__engine.py --emit-yaml > utilities/<id>.yaml
```

If the config is wrong (an unknown icon, a missing key, unreadable JSON), `--emit-yaml` prints the problem on screen (for an icon it also lists the valid names), writes nothing to stdout and exits 1. The shell still creates an empty `utilities/<id>.yaml` for `>`: an empty file means the command failed, so run it again without `> ...` to read the reason. `run`, `lint` and `check` say the same when they meet an app file that is empty or is not YAML.

The engine never connects to anything unless `api.fixture_default` is `false` (or `BOLT_APP_FIXTURE=1` is unset and the config says live).

## Modes (`mode`)

| mode | Use it for | Needs |
|---|---|---|
| `views` (default) | Overview tiles that drill into lists, detail views, filters | `endpoints`, `overview`, `views` |
| `form` | A typed input form, then a result pane | `form` |
| `lookup` | One word in, one detail card out | `endpoints`, `lookup` |

## Two shapes of app: lookup or views

Pick before you build: the two shapes cannot be mixed in one app.

| | `lookup` | `views` |
|---|---|---|
| The person types | a word (up to three): `=chip serde` | a view name, then optionally one word: `=chip customers acme` |
| The word reaches | the API, as `{query}` in an endpoint path (URL-quoted) | nothing remote: it filters the list the endpoint already returned |
| Drill and Back | none | yes (`nav` rows, `children`, Back row) |
| Right pane | one for the result | one per view, from `views[].widget` |
| Buttons on a row | Open (`url`) and Copy; see "Buttons in lookup mode" | Open and Copy in config; more in the app file's `actions:` |

What a views-mode app does with a typed first word, from the engine and the launcher (written from source, run here only in sample mode): a first word that is not a declared view is not an error, but the engine ignores it and prints the overview rows, which the app-level right pane draws. So a views-mode app cannot take a typed query. What it can take: `=chip <view> <word>` keeps the rows of that view whose title, subtitle, badge or first five fields contain the word (case-insensitive, one word; a "Showing N of M" row clears it), and `=chip <view> <id>` opens one row when that view has `children`.

**Recipe: type a name, see a summary, drill into related lists (views mode).** It works when the API's list endpoints already return every row you need (the engine filters on this side, up to the row limits in the rules table):

```
"endpoints": { "customers": { "path": "/customers" }, "orders": { "path": "/orders" } },
"views": [
  { "id": "customers", "title": "Customers", "endpoint": "customers",
    "children": [{ "view": "orders", "match": "customer_id" }],
    "item": { "title": "{name}", "subtitle": "{plan} · {city}", "fields": [{ "label": "Plan", "value": "{plan}" }] } },
  { "id": "orders", "title": "Orders", "endpoint": "orders",
    "item": { "title": "{number}", "subtitle": "{total|round2} · {status}" } } ]
```

The person types `=chip customers acme`, sees the customers that match (each row is a summary), presses Enter on one to see its summary with its orders listed below, and Back returns to the filtered list. The portal-template example is this shape (projects, each with its tickets).

**Not possible in one app on 181:** "type a name, ask the API for exactly that name, then drill". Asking the API per word needs `lookup`, and lookup has no drill. The honest workaround is two apps: a `lookup` app for the typed name (rows, Open, Copy) and a `views` app for browsing (its own chip), or a script app that reads its own words (see `repo-radar`, and "Typing free text and views in a script app" below).

## `app`
`id` (folder name), `chip` (the word typed after `=`), `title`, `icon` (a launcher icon name), `description`, `service` (name used in error rows), `searchable` (accepted and does nothing: once the app has rows, Bolt filters them as you type, matching the title and subtitle only; an app with `dispatch.choices` shows its confirm choices instead), `timeout` (seconds, 1 to 60).

## `api` (views and lookup)
`on_missing_key` (`setup` or `sample`; see "Three starting states" below), `base_url` (https, or loopback http for tests), `key_env` (variable name), `env_file` (a `.env` path, must be `chmod 600`), `auth_header`, `auth_prefix` (`"Bearer "`), `fixture_default` (true = sample data, no network), `fixture_file`, `fixture_banner` (show a Sample data row). `allowed_hosts` (extra https hosts an endpoint `path` may name; the key is sent only to the `base_url` host), `auth_in` (`header`, the default, or `query`), `auth_param` (the query parameter name for `auth_in: query`, default `api_key`; the key is stripped from every answer before it is cached or shown, so prefer a header when the API allows one), `user_agent`.

## `cache`
`ttl` seconds a result is fresh (a repeat run inside it makes no request), `stale_max` seconds an old copy may be shown when the API fails. A failed call is never cached and never shown as zero.

## `endpoints`
`name: { path, kind (list or object), data (where the rows sit in the response, default "data"), map }`. `map` renames fields: `{ "title": "name", "owner": "assignee.name" }` (dotted paths work). Fixture mode reads `fixtures.json[name]`, the raw response. `fixtures.json` may also hold `_now` (epoch seconds: a fixed clock for the date tokens in sample mode) and, for a form app, `seed` (sample rows shown after the saved ones).

More endpoint options: `hydrate` (`{ path, limit }`: the answer is a list of ids and `path` contains `{id}`; one request per id runs in parallel, `limit` 1 to 50, default 20; an id that fails is dropped; if none answer the endpoint fails), `flatten` (`true` or a field name: an object of lists keyed by date or name becomes one list, the key kept in that field, default `key`), `require` (on an object endpoint: dotted paths that must be present, otherwise the answer counts as failed, never as zero). A `path` may use the date tokens `{today}`, `{today-7d}` and `{today+1d}` (local dates, 0 to 9999 days). An answer that says there is more (a next link or cursor, `has_more`, or a total above the rows held; read from the answer, `meta` or `pagination`) shows a "first page only" notice.

## `stats` (named numbers for the overview)
`{ endpoint, where, group }` counts rows. `where`: `{ "status": ["done"] }`, `{ "status": { "not": ["done"] } }`, `{ "n": { "gte": 1 } }`. `group` gives "7 a, 3 b". `{ "pct": [a, b] }` and `{ "sum": [a, b] }` combine other stats.

## `overview.rows[]`
`title`, `subtitle`, `icon`, `body`, `view` (drill to a view; `arg` filters it), `url` (opens a link), `tile`, `extra`, `trend` (list of numbers), `only_if`. `overview.widget` replaces the default tiles pane.

## `tile`
`{ label, value (a stat or field name, or a number), max, unit (4 characters), note, foot, badge }`. `badge` is a word or a list of `{ "if": "ready>=80", "badge": "ON TRACK" }` rules, first match wins, last one without `if`.

## `views[]`
`id` (view count: see [the rules table](QUICKSTART.md#4-the-rules-table)), `title`, `icon`, `endpoint`, `sort` (`[{ field, order[], desc }]`), `children` (`[{ view, match }]` drills to rows of another view whose `match` field equals this row's id), `no_children`, `empty`, `widget` (`{ kind, mode, bind }`, copied into the app file; default is a detail preview built from `item.fields`). Pane kinds with app data: card, markdown, entity_preview, chart, table, cards, detail, json_tree, diff, image_grid (the same list as the rules table; chart types are line, bar and sparkline only).

More view options: `id_field` (the row field that holds its id, default `id`), `pane_id` (the pane name the rows use, default the view id), and on a `children` entry `parent_field` (the row field compared to `match`, default the view's `id_field`).

`item`: `title`, `subtitle`, `icon`, `url`, `body` (markdown), `copy`, `tile`, `fields` (up to 5 `{ label, value, kind }`), `extra` (named row fields a widget binds as `{{row.name}}`; a value that is exactly `{field}` keeps a number a number), `data_field` (a nested object for a json_tree pane), `trend_field`. A field named `left`, `right` or ending `_lines` keeps line breaks.

Templates use `{field}` and `{field|filter}`: `human`, `day`, `hhmm`, `when` (an epoch in seconds or milliseconds as local `2026-11-15 14:05`), `whenday` (the same, date only), `round`, `round1`, `round2` (a number to 0, 1 or 2 decimals), `upper`, `lower`, `yes`, `join`, `dots`, `count`, and any name from `maps`. A missing value reads `unknown`.

## Words typed after the chip (views mode)
`=chip view`, `=chip view <id>` (detail), `=chip view <word>` (filter by that word), `=chip view demo-offline | demo-stale | demo-auth | demo-nokey` (preview the error rows in fixture mode). A view whose widget `mode` is `list_data` (chart, table) shows only its data rows, so nothing but data is plotted.

## `form`
`inputs[]` (`name`, `type` text, number, date, select or toggle, `label`, `required`, `default`, `placeholder`, `options`, `min`, `max`, `step`, `max_length`, `pattern`), `submit.label`, `store.file` (a local log, kept `0600`; `max_rows`), `record` (what is saved, templates over the input values), `item` (how a saved row becomes a result row), `widget`. Bad input shows one "Not saved" row and saves nothing.

## `lookup`
`endpoint`, `match` (fields compared to the typed word: exact first, then contains), `item`, `widget`, `prompt_title`, `prompt_subtitle`, `none_title`, `examples`.

### Buttons in lookup mode
A lookup row has Open (when its `url` renders to an https address) and Copy, and nothing else: no nav, no drill, no Back, no per-row actions. What Copy puts on the clipboard depends on the form of the lookup:
- `endpoint` + `match` + `item` (one endpoint): `item.copy` (a template) is honoured; with none, Copy copies the row text.
- `steps` + `rows` (a chain): each `rows[]` entry is drawn like an overview row, so its `copy` is ignored and Copy copies the row text. The check command warns about it (config_copy_ignored). Put the text you want copied in `title` or `subtitle`.

## Files named in the command
The app file lists `<id>__config.json`, `<id>__fixtures.json` and `<id>__bolt_app_kit.py` after the script, so Bolt includes them in what the person approves and asks again if any changes. The engine ignores them as input.

## Commands

```
./bolt-apps kit vendor --flat kit/examples/<id>     # once, and after a kit update
./bolt-apps check kit/examples/<id> --update-golden # review golden/ once
./bolt-apps check kit/examples/<id>
./bolt-apps lint kit/examples/<id> --personal
./bolt-apps pack kit/examples/<id> --personal --version 1.0.1   # a higher version each time
```
Run `./bolt-apps keygen` once before the first pack (it makes your signing key and never overwrites one). Drop the `.boltpack` on the Bolt launcher or Bolt Apps.

## Where to store keys (measured against the launcher)

Bolt starts a personal app's script with an empty environment except a short allowlist (listed in [the rules table](QUICKSTART.md#4-the-rules-table), from `schema/bolt-rules.json` `runner_env`). A name that looks secret (it contains TOKEN, KEY, SECRET, PASS, PWD, CRED, AUTH, PRIVATE, SESSION or COOKIE) is never forwarded to a personal or packed app, and `bridge.env` is refused if it lists one; only apps shipped inside Bolt may forward them. So an environment variable in your shell does NOT reach the script when Bolt runs it. It works only in a terminal and in tests.

| Place | Works in Bolt | Good | Bad |
|---|---|---|---|
| System keychain (macOS `security`, Linux `secret-tool`) | yes | encrypted at rest, per user, never a file | not available on Windows here; needs the tool installed |
| `~/.config/<app id>/.env`, mode 0600 | yes (the script runs as you and can read it. The install checks do not require a declared permission for this, but list `files` in `bolt-app.json` so the listing is honest) | works everywhere, one line to set up | plain text on disk; the engine refuses it if others can read it |
| Environment variable | terminal and tests only | handy for CI | never reaches the script under Bolt |
| `inputs: type: secret` form field | accepted by the launcher; not used by these examples | typed once | the value is passed to the command as a word; not measured for the run log, so do not rely on it |

The engine (and any kit app) reads the key with `kit.get_secret(app_id, NAME, env_file=...)`: environment, then keychain, then the `.env` file. When nothing is found it shows a row with the exact one-line setup (`kit.setup_hint`). `kit.redact(text, [key])` removes the key, `user:password@` in an address and key-like query values from any text before it is shown.

Never put a key: in the app file, in `config.json`, in `fixtures.json`, in a pack, in the cache, in a query word, in row text, in an error message, in a URL you show or log. The runner also masks the values of names it forwards, but a script that reads its own key is on its own: use `redact`.

Expected install-prompt finding: an app that reads the keychain is listed as "the system keychain or the security command". That is true, so it is left in.

## More options
- `lookup.steps` + `lookup.rows`: a chain of endpoints; a step's `path` may use `{query}` and `{earlier_step.field}` (the first result of an earlier step), values are URL-quoted. An endpoint `path` that starts with `https://` is used as is (a second host).
- `maps`: `{ "wmo": { "0": "Clear" } }`, used as `{field|wmo}`. Filter `hhmm` cuts `2026-01-01T05:30` to `05:30`.
- `trend_path` on an overview or lookup row: a dotted path to a number list for a tile sparkline.
- Stats `{ endpoint, field_sum }` and `{ endpoint, field_max }` total or maximise a field.
- `api.key_env` is optional: leave it out for a keyless API. `api.user_agent` sets the User-Agent header.
- A chart or table view (widget mode `list_data`) has no Back or refresh rows.

## What backs your app (the coverage matrix)

| Backing | Runtime | How | Start from | Limits |
|---|---|---|---|---|
| CLI command | `bridge` | a script runs the command as an argument list, no shell | `cli-wrapper-template`, `system-glance` | personal pack only; per-OS command table; stderr is not seen; 60 s at most |
| Remote HTTP API | `bridge` | a script calls the API inside a deadline; one config-only API through this engine | `repo-radar`, `around` (several joined), `lookup-template` and the engine apps (one API) | declare `network`; keys from keychain or `~/.config/<app>/.env` |
| Local HTTP service | `http_local` | one GET or POST to loopback, no script | `local-service-template` | loopback only, one request, no secrets, no chaining |
| File | `bridge` | a script reads a typed path with caps | `file-insights-template`, `form-template` | declare `files`; a path cannot travel in a row's nav arg, so keep the last path in the kit cache |
| MCP server | none native | a bridge script starts the server over stdio (below) | the snippet below | tested only against a stand-in server |

These examples are not driven by `engine.py`: `file-insights-template`, `cli-wrapper-template`, `repo-radar` and `around` each have their own script on the same flat kit, with `config.json` holding what changes (columns, command table, weights, TTLs) and `--emit-yaml` generating the app file. Their entries in `index.json` say `custom script on the flat kit`.

Launcher facts measured for these examples: pane kinds and limits are in [the rules table](QUICKSTART.md#4-the-rules-table) (a place opens with an Open in Maps URL action, not a map pane); the chart title is the `label` bind written as literal text; a nav arg is one plain token, so repeat the typed query from the kit cache; the bridge command must name every helper file as `{{scripts_dir}}/<file>`.

## MCP: the workaround script

Bolt has no native MCP runtime for a personal app. A `bridge` script can stand in: start the server the person already has installed, speak JSON-RPC over its pipes, call one tool, and print rows. It was run against a stand-in stdio server that answers `initialize` and `tools/call`; it has not been run against a real MCP server, so treat it as a starting point. Put `{"server": ["npx", "-y", "some-mcp-server"], "tool": "search", "arg": "query"}` in `scripts/<id>__config.json`, declare `runs_commands`, and name `config.json` and `bolt_app_kit.py` in the bridge command.

```python
import json, os, subprocess, sys, threading
import importlib.util as _u
_me = os.path.basename(__file__); _pfx = _me.partition("__")[0] + "__"     # <app id>__ : every file of this app starts with it
_s = _u.spec_from_file_location("bolt_app_kit", os.path.join(os.path.dirname(os.path.abspath(__file__)), _pfx + "bolt_app_kit.py"))
kit = _u.module_from_spec(_s); sys.modules["bolt_app_kit"] = kit; _s.loader.exec_module(kit)
cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), _pfx + "config.json")))

def main(argv):
    word = " ".join(w for w in argv[1:] if w != "-" and not w.endswith(("config.json", "bolt_app_kit.py"))   # the helper files named in the command)[:200]
    if not word:
        kit.emit([kit.row("Type a query", "sent to the %s tool" % cfg["tool"], copy=False)])
    exe = kit.which(cfg["server"][0])
    if not exe:
        kit.emit([kit.error_row("%s is not installed" % cfg["server"][0], title="MCP server not found")])
    p = subprocess.Popen([exe] + cfg["server"][1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    threading.Timer(15, p.kill).start()        # a hung server must not hold the launcher
    def rpc(i, method, params):
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}) + "\n"); p.stdin.flush()
        while True:
            line = p.stdout.readline()
            if not line:
                raise RuntimeError("server closed")
            m = json.loads(line)
            if m.get("id") == i:
                return m
    try:
        rpc(1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "bolt-app", "version": "1"}})
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"); p.stdin.flush()
        r = rpc(2, "tools/call", {"name": cfg["tool"], "arguments": {cfg["arg"]: word}})
    except Exception as e:
        kit.emit([kit.error_row("The MCP server did not answer (%s)" % e.__class__.__name__, title="MCP call failed")])
    finally:
        p.kill()
    texts = [c.get("text", "") for c in (r.get("result") or {}).get("content", []) if c.get("type") == "text"]
    kit.emit([kit.row(t.splitlines()[0][:100] if t else "(empty)", "tool %s" % cfg["tool"], body=t, icon="Terminal") for t in texts]
             or [kit.error_row(str((r.get("error") or {}).get("message", "no content"))[:120])])

main(sys.argv)
```
Limits: servers that need a login or a key are out of scope here (use `get_secret` and pass the key in the server's environment from the script, never in `config.json`); the server starts on every run, so slow servers feel slow; remote MCP servers over HTTP are a plain HTTP call and need no workaround.

## An app that only shows sample data (offline, no API)

Most apps ship live (`api.fixture_default` `false`). An app that is sample-only by design (a demo, a reference card, a checklist whose data you write yourself) ships with the sample switch on, so it never opens a connection:

```
"api": { "base_url": "https://example.invalid", "fixture_default": true, "fixture_file": "fixtures.json" }
```

- `base_url` is still required by the config check; use a name that cannot resolve, such as `https://example.invalid`. Nothing connects to it while `fixture_default` is `true`.
- `fixtures.json[<endpoint name>]` holds your rows, shaped like an API answer. It is signed with the pack, so changing the data means reshipping.
- Leave out `key_env`: no key, no setup row. `on_missing_key` does nothing here.
- `fixture_banner` (default off) adds a row or tile note that says the data is sample. Turn it on when the person might take your rows for real data. Label real-looking rows yourself too (a `SAMPLE` badge, "invented" in the body) if they could be mistaken for facts.
- `ship` and `doctor` read the same words: "Start mode: sample data (api.fixture_default is true), so it never contacts a service." If the same config also names a `key_env`, both add that the key is never read and the app never goes live.
- QUICKSTART rule 4 ("ship live") has this one exception: sample-only by design. If the app is meant to show someone's real data, `fixture_default` must be `false`.

## Sample mode, live mode and what check does

- A shipped engine app is live (`api.fixture_default` is `false`) unless it is sample-only by design (see "An app that only shows sample data" above). An installed pack cannot be switched between the two, because `config.json` is signed and Bolt starts the script with no environment.
- `check` runs the script in sample mode so tests need no key and no network: put `"fixture": true` at the top of `check.json` (every case) or on one case (a case wins over the top level; `"fixture": false` forces live). The script then reads `fixtures.json`. A terminal run can use `BOLT_APP_FIXTURE=1` (or `0`).
- Live with no key shows one setup row with the exact one-line command. Live with the network down shows the offline row, or an old copy with its age when one was cached. These are checked in sample mode with `demo-nokey`, `demo-offline`, `demo-auth` and `demo-stale`.

## What check tells you

- `expected_text_missing` now prints the first rows that were found, so you can copy the real text.
- If the script printed its own error row ("This app is not set up correctly", "This app could not run"), `check` reports `app_error_row` with that row's text, for example a bad icon name in `config.json`, before it looks at expected text.
- Every `icon` in `config.json` (the app, overview rows, views, items) must be a name in `kit/schema/icons.json`. The engine refuses an unknown name with its place (`views[0].icon`), and `lint --personal` reports `icon_unknown`: an error for `scripts/<id>__config.json` (the kit refuses the row) and a warning for the app file's own `icon:` (the launcher draws a plain plug and still shows the app).
- A file in `golden/` that no case names is `golden_stale`. A copied template brings its goldens: keep the cases you want, delete the other goldens, then run `check --update-golden` once and read the files.
- Stubs can answer by argument, so a tool called as `git status` and `git log` can be tested: `"stubs": {"git": {"stdout": "default", "by_args": [{"args": ["status", "--porcelain"], "file": "fixtures/macos/status.out"}, {"args": ["log"], "stdout": "abc123 first", "rc": 0}]}}`. The first rule whose words equal the first words of the command line answers; the stub's own `stdout` or `file` is the default. A case can set environment variables with `"env": {"MYVAR": "value"}` (names in capitals; `PATH` is always the stub folder and `HOME` a temporary folder).

## Permissions: which list wins

`bolt-app.json` `permissions` is listing text. The install prompt and `verify` show the permissions computed from the app files (`runs_commands`, `inserts_text`, `opens_links:<host>`, `network:localhost:<port>`). A declared `network` or `files` for a bridge script is never computed, shown or checked. `lint --personal` warns with `permissions_differ` when the two disagree and says which words are computed but not declared and which are declared but not computed. Keep a declared word only if it is true of the app.

## Limits of views mode (so you pick the right template)

- Views mode calls the list endpoints you name; it cannot call a per-id detail endpoint. `{id}`-style paths (and `{query}`) work only in `lookup` mode, where one typed word drives the calls. For a detail view, put the detail fields in the list response, or use a `lookup` app, or write a script like `repo-radar`.
- Row actions in config are only Open (`url` on an item) and Copy (`copy`). More buttons need the app file's `actions:` (kinds `url`, `composer`, `utility`, `run`; the count limit is in [the rules table](QUICKSTART.md#4-the-rules-table), and Open and Copy count), and a nav row carries no actions.
- Stitching: stats from several endpoints on the overview, and `children` that list rows of another view whose field equals this row's id. There is no cross-join of two endpoints into one row. For that, use a script (`repo-radar` joins on a repo and its package; `around` stitches by distance).
- Lists are capped by the engine (row limits: [the rules table](QUICKSTART.md#4-the-rules-table)); the view says so.

## Which file to edit in each template

The `edit` list of each template in [index.json](index.json) is the one answer (a test checks the files exist). A template with no `edit_in_script` entry needs no script change. For a CLI app you are expected to edit `build()` in `scripts/<id>__wrap.py`, because the rows depend on what your tool prints. `scripts/<id>__fixtures.json` holds a sample so a copy works before the tool is installed.

Never edit `<id>__bolt_app_kit.py`: re-vendor it with `bolt-apps kit vendor --flat <app>`. Every file in `scripts/` is named `<id>__<name>`: all installed apps share one scripts folder, and Bolt refuses a file another app already owns (`owned_by_other`). Every script that lists a helper file in its command names it as `{{scripts_dir}}/<id>__<file>` (`<id>__config.json`, `<id>__fixtures.json`, `<id>__bolt_app_kit.py`) so Bolt shows it in the approval.

## Typing free text and views in a script app

The view is read from query word 0 (`view_arg` bound to `query.word(0)`), so a script app that also takes free text treats the first word as a view only when it is one of its view names and otherwise reads every word as text (`=insights ~/data.csv`, `=insights trend`). A text that starts with a view name needs a leading `./` or a different spelling. Words before the view word would need plain-word defaults (lint `view_arg_lead_default`); a default of `-` is fine for words after it. A nav row carries no actions and cannot carry text with a slash; keep the last typed text in the kit cache. To give a drilled-in view a button, add an ordinary row with `kit.action_chain(id, label, target_chip, query)` pointing at the app's own chip: a utility action to itself. That is not yet proven in the launcher.

## Three starting states (`api.key_env` and `api.on_missing_key`)

1. **Live with a key.** The key is found (environment, keychain or `~/.config/<id>/.env`): the app calls its API and shows real data.
2. **Sample fallback** (`"on_missing_key": "sample"`, for demos whose API is fictional): no key, so the app shows its labelled sample data and never replaces it. Where the view is a tiles grid (a row with no number draws an empty "-" tile) the label rides on real tiles: the badge says SAMPLE, a footer says "sample data: add your ... API key for live data" (or the first tile's note, when every footer is in use; real data is never overwritten). Every other view keeps two visible rows: "SAMPLE DATA: add your ... API key to see live data" and a key-hint row. Chart and table data views carry neither, because the row would become a data point. A tiles overview also has no Refresh row for the same reason.
3. **Setup only** (`"on_missing_key": "setup"`, the default, for a real app): no key, so the app shows one row that says how to add it. That row carries no tile and no pane.

`BOLT_APP_FIXTURE=1` always shows sample data, and says so only for an app with `api.fixture_banner` set (the other demos show the data without a label in that mode, which is a test and terminal mode), `0` always goes live. The SAMPLE DATA and key-hint rows of state 2 are left out of chart and table views, where a label row would become a data point. A key file with open permissions keeps its own "tighten the permissions" row and is never replaced by sample data. `on_missing_key` must be `setup` or `sample`. `bolt-apps ship` and `bolt-apps doctor <folder>` say which state the app starts in.

