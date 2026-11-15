# The shared engine: every config option, once

All apps here run the same `scripts/engine.py`. An app is `scripts/config.json` plus `scripts/fixtures.json`. Nothing else is edited. Regenerate the app file after any change:

```
python3 scripts/engine.py --emit-yaml > utilities/<id>.yaml
```

The engine never connects to anything unless `api.fixture_default` is `false` (or `BOLT_APP_FIXTURE=1` is unset and the config says live).

## Modes (`mode`)

| mode | Use it for | Needs |
|---|---|---|
| `views` (default) | Overview tiles that drill into lists, detail views, filters | `endpoints`, `overview`, `views` |
| `form` | A typed input form, then a result pane | `form` |
| `lookup` | One word in, one detail card out | `endpoints`, `lookup` |

## `app`
`id` (folder name), `chip` (the word typed after `=`), `title`, `icon` (a launcher icon name), `description`, `service` (name used in error rows), `searchable` (true lets the launcher filter rows as you type), `timeout` (seconds, 1 to 60).

## `api` (views and lookup)
`base_url` (https, or loopback http for tests), `key_env` (variable name), `env_file` (a `.env` path, must be `chmod 600`), `auth_header`, `auth_prefix` (`"Bearer "`), `fixture_default` (true = sample data, no network), `fixture_file`, `fixture_banner` (show a Sample data row).

## `cache`
`ttl` seconds a result is fresh (a repeat run inside it makes no request), `stale_max` seconds an old copy may be shown when the API fails. A failed call is never cached and never shown as zero.

## `endpoints`
`name: { path, kind (list or object), data (where the rows sit in the response, default "data"), map }`. `map` renames fields: `{ "title": "name", "owner": "assignee.name" }` (dotted paths work). Fixture mode reads `fixtures.json[name]`, the raw response.

## `stats` (named numbers for the overview)
`{ endpoint, where, group }` counts rows. `where`: `{ "status": ["done"] }`, `{ "status": { "not": ["done"] } }`, `{ "n": { "gte": 1 } }`. `group` gives "7 a, 3 b". `{ "pct": [a, b] }` and `{ "sum": [a, b] }` combine other stats.

## `overview.rows[]`
`title`, `subtitle`, `icon`, `body`, `view` (drill to a view; `arg` filters it), `url` (opens a link), `tile`, `extra`, `trend` (list of numbers), `only_if`. `overview.widget` replaces the default tiles pane.

## `tile`
`{ label, value (a stat or field name, or a number), max, unit (4 characters), note, foot, badge }`. `badge` is a word or a list of `{ "if": "ready>=80", "badge": "ON TRACK" }` rules, first match wins, last one without `if`.

## `views[]`
`id` (at most 7 views besides overview: the launcher refuses more), `title`, `icon`, `endpoint`, `sort` (`[{ field, order[], desc }]`), `children` (`[{ view, match }]` drills to rows of another view whose `match` field equals this row's id), `no_children`, `empty`, `widget` (`{ kind, mode, bind }`, copied into the app file; default is a detail preview built from `item.fields`).

`item`: `title`, `subtitle`, `icon`, `url`, `body` (markdown), `copy`, `tile`, `fields` (up to 5 `{ label, value, kind }`), `extra` (named row fields a widget binds as `{{row.name}}`; a value that is exactly `{field}` keeps a number a number), `data_field` (a nested object for a json_tree pane), `trend_field`. A field named `left`, `right` or ending `_lines` keeps line breaks.

Templates use `{field}` and `{field|filter}`: `human`, `day`, `upper`, `lower`, `yes`, `join`, `dots`, `count`. A missing value reads `unknown`.

## Words typed after the chip (views mode)
`=chip view`, `=chip view <id>` (detail), `=chip view <word>` (filter by that word), `=chip view demo-offline | demo-stale | demo-auth | demo-nokey` (preview the error rows in fixture mode). A view whose widget `mode` is `list_data` (chart, table) shows only its data rows, so nothing but data is plotted.

## `form`
`inputs[]` (`name`, `type` text, number, date, select or toggle, `label`, `required`, `default`, `placeholder`, `options`, `min`, `max`, `step`, `max_length`, `pattern`), `submit.label`, `store.file` (a local log, kept `0600`; `max_rows`), `record` (what is saved, templates over the input values), `item` (how a saved row becomes a result row), `widget`. Bad input shows one "Not saved" row and saves nothing.

## `lookup`
`endpoint`, `match` (fields compared to the typed word: exact first, then contains), `item`, `widget`, `prompt_title`, `none_title`, `examples`.

## Files named in the command
The app file lists `config.json`, `fixtures.json` and `bolt_app_kit.py` after the script, so Bolt includes them in what the person approves and asks again if any changes. The engine ignores them as input.

## Commands

```
node toolkit/bin/bolt-apps.mjs kit vendor --flat kit/examples/<id>     # once, and after a kit update
node toolkit/bin/bolt-apps.mjs check kit/examples/<id> --update-golden # review golden/ once
node toolkit/bin/bolt-apps.mjs check kit/examples/<id>
node toolkit/bin/bolt-apps.mjs lint kit/examples/<id> --personal
node toolkit/bin/bolt-apps.mjs pack kit/examples/<id> --personal --version 1.0.1   # a higher version each time
```
Run `node toolkit/bin/bolt-apps.mjs keygen` once before the first pack (it makes your signing key and never overwrites one). Drop the `.boltpack` on the Bolt launcher or Bolt Apps.

## Where to store keys (measured against the launcher)

Bolt starts a personal app's script with an empty environment except a short allowlist: HOME, PATH, USER, LANG, TERM, TMPDIR, TZ, LC_*, XDG_* and the certificate bundle variables. A name that looks secret (it contains TOKEN, KEY, SECRET, PASS, PWD, CRED, AUTH, PRIVATE, SESSION or COOKIE) is never forwarded to a personal or packed app, and `bridge.env` is refused if it lists one; only apps shipped inside Bolt may forward them. So an environment variable in your shell does NOT reach the script when Bolt runs it. It works only in a terminal and in tests.

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

Launcher facts measured for these examples: a personal app cannot show data in `right_widget` kinds `image`, `color`, `weather`, `date`, `calc` or `map` (use an Open in Maps URL action); chart types are `line`, `bar` and `sparkline` only, and the chart title is the `label` bind written as literal text; at most 8 views including the overview; a nav arg is one plain token (no slash), so repeat the typed query from the kit cache; the bridge command must name every helper file as `{{scripts_dir}}/<file>`.

## MCP: the workaround script

Bolt has no native MCP runtime for a personal app. A `bridge` script can stand in: start the server the person already has installed, speak JSON-RPC over its pipes, call one tool, and print rows. It was run against a stand-in stdio server that answers `initialize` and `tools/call`; it has not been run against a real MCP server, so treat it as a starting point. Put `{"server": ["npx", "-y", "some-mcp-server"], "tool": "search", "arg": "query"}` in `scripts/config.json`, declare `runs_commands`, and name `config.json` and `bolt_app_kit.py` in the bridge command.

```python
import json, os, subprocess, sys, threading
import bolt_app_kit as kit
cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")))

def main(argv):
    word = " ".join(w for w in argv[1:] if w != "-" and not w.endswith(("config.json", "bolt_app_kit.py")))[:200]
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
