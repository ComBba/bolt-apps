# What a Bolt App can do

_Generated from `capabilities.json` by `scripts/build-capabilities.mjs`: edit the JSON, not this file._

One row per capability. Status is derived from the code and `schema/bolt-rules.json`. Nothing here is verified in real Bolt yet. The sandbox is not shipped: a personal script runs as you. To start, read [QUICKSTART.md](QUICKSTART.md); the limits are in its one rules table.

| Capability | Status | Example | Proven by | Limit |
|---|---|---|---|---|
| Pane: card | supported | [widget-gallery-2](widget-gallery-2) | `kit/examples/widget-gallery-2/check.json` | One card for the selected row. Strings in bind: up to 4096 characters. |
| Pane: markdown | supported | [widget-gallery](widget-gallery) | `kit/examples/widget-gallery/check.json` | Body up to 16384 characters. |
| Pane: entity_preview | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | Facts list up to 40 entries, one tile above. Config default for a detail view. |
| Pane: chart | supported | [widget-gallery](widget-gallery) | `kit/examples/widget-gallery/check.json` | Types line, bar and sparkline only. Title is the label bind as literal text. |
| Pane: table | supported | [widget-gallery](widget-gallery) | `kit/examples/widget-gallery/check.json` | Up to 40 columns; totals sum, avg, min, max, count; the engine hands it at most 50 rows. |
| Pane: cards | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | Layout tiles or grid; tile label cut at 24 characters. |
| Pane: detail | supported | [widget-gallery](widget-gallery) | `kit/examples/widget-gallery/check.json` | Label and value fields of the selected row. |
| Pane: json_tree | supported | [widget-gallery](widget-gallery) | `kit/examples/widget-gallery/check.json` | Reads a nested object from the row field named in bind.source. |
| Pane: diff | supported | [widget-gallery](widget-gallery) | `kit/examples/widget-gallery/check.json` | Two texts, line by line. |
| Pane: image_grid | supported | [widget-gallery-2](widget-gallery-2) | `kit/examples/widget-gallery-2/check.json` | 1 to 8 columns. Inline data images only in the examples. |
| Panes: map, image, color, weather, date, calc | not supported | none | `toolkit/test/launcher-rules.test.mjs` | A personal app cannot show its own data in these panes: Bolt shows "cannot show app data". Use table, detail, cards or chart. |
| Chart types: pie, donut, area, multi-series, heatmap, gauge | not supported | none | `toolkit/test/bolt-rules.test.mjs` | Not shipped. Only line, bar and sparkline draw. Do not use any other chart type. |
| Left list: list, table, cards, detail | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | presentation.widget is one of list, table, cards, detail. |
| Several views in one app | supported | [acme-dash](acme-dash) | `kit/examples/acme-dash/check.json` | At most 8 views including the overview; view ids match `^[a-z][a-z0-9_-]{0,23}$`. |
| Drill from an overview row to a list | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | A nav arg is one plain token matching `^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$`; no slash. |
| Back row on a drilled-in view | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | A nav row carries no actions. |
| Drill from a row to related rows of another view | supported | [acme-dash](acme-dash) | `kit/examples/acme-dash/check.json` | The related view lists rows whose match field equals this row id. No cross-join of two endpoints. |
| Row id from another field (id_field, parent_field) | supported | [feed-template](feed-template) | `kit/examples/feed-template/check.json` | id_field names the row field used as the id (default id); parent_field is on a children entry. A nav arg is one token, so an id with a space does not work. |
| Filter a list by a typed word | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | The word filters title, subtitle, badge and the first 5 fields. It is the second word typed; there is no filter field in a row. |
| Launcher filters rows as you type | supported | [table-template](table-template) | `kit/examples/table-template/check.json` | Set app.searchable to true; the launcher does the filtering on the rows shown. |
| Fresh cache and a stale copy when the API fails | supported | [portal-template](portal-template) | `kit/python/tests/test_cache_rows.py` | ttl seconds a result is fresh; stale_max seconds an old copy may be shown with its age. A failed call is never cached or shown as zero. |
| A detail pane that changes with the selected row | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | Each view has its own pane through `presentation.views.<id>.right_widget`. |
| Number tiles with a meter, unit, note and badge rules | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | Unit at most 4 characters; trend keeps 30 points. |
| Footer buttons (url, composer, utility) | supported | [acme-dash](acme-dash) | `kit/examples/acme-dash/check.json` | Bolt shows at most 6 footer buttons; the kit and engine keep to 3 (Open and Copy count). Bolt keeps 40 label characters; the button shows 14. |
| Run action: one click runs this app with a fixed query | supported | no example yet; copy the snippet | `toolkit/test/launcher-rules.test.mjs` | kind run needs a query_template of fixed text. No example yet. |
| Footer button icon | supported | no example yet; copy the snippet | `toolkit/test/bolt-rules.test.mjs` | Icon names are lowercase and case-sensitive, from the list in schema/bolt-rules.json (actions.icons); anything else is refused. |
| Open a place in Maps from a row (instead of a map pane) | supported | [places-list](places-list) | `kit/examples/places-list/check.json` | A personal app cannot draw the map pane; the row Open button opens the place in a browser. |
| Row actions: Open and Copy from config | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | Config rows carry Open (url) and Copy (copy) only; more buttons need the app file actions. |
| Icons in config.json and the app file | supported | [portal-template](portal-template) | `kit/python/tests/test_review_engine.py` | Icon names are case-sensitive: config.json names come from kit/schema/icons.json; footer-action icons come from actions.icons. |
| Typed input form with validation | supported | [form-template](form-template) | `kit/examples/form-template/check.json` | Types text, number, date, select, toggle. Bad input shows one "Not saved" row and saves nothing. |
| Secret input field | partial | no example: not recommended | `toolkit/test/bolt-rules.test.mjs` | The launcher accepts type secret but the value reaches the script as a plain word and the run log is not measured. Use the keychain or a 0600 .env file. |
| REST list endpoint | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | GET only; at most 50 rows per list; 10 s per request, 14 s together. |
| A list of ids, then one request per id | supported | [feed-template](feed-template) | `kit/python/tests/test_round2_engine.py` | limit 1 to 50; requests run in parallel; ids that fail are dropped. |
| API key sent as a query parameter | supported | [script-template](script-template) | `kit/python/tests/test_round2_engine.py` | The key is stripped from the answer before anything is cached or shown. Prefer a header when the API allows it. |
| API key sent in a header | supported | [portal-template](portal-template) | `kit/examples/portal-template/check.json` | The key goes only to the host of base_url. |
| No key at all | supported | [lookup-template](lookup-template) | `kit/examples/lookup-template/check.json` | Leave key_env out. |
| Date tokens in a path: {today}, {today-7d}, {today+1d} | supported | [feed-template](feed-template) | `kit/python/tests/test_round2_engine.py` | Local dates, 0 to 9999 days; sample mode uses _now from fixtures.json. |
| An object of lists keyed by date or name | supported | [feed-template](feed-template) | `kit/python/tests/test_round2_engine.py` | flatten is true or the field name that keeps the key; keys sort. |
| A second host for one endpoint | supported | [lookup-template](lookup-template) | `kit/examples/lookup-template/check.json` | Full addresses must be https on the base_url host or a host in allowed_hosts. The key is never sent to a second host. |
| Refuse an answer that lacks fields | supported | [lookup-template](lookup-template) | `kit/examples/lookup-template/check.json` | On an object endpoint; an answer without them counts as failed, never as zero. |
| Chain endpoints: one answer feeds the next path | supported | [lookup-template](lookup-template) | `kit/examples/lookup-template/check.json` | Lookup mode only: {earlier_step.field} and {query}; values are URL-quoted. Views mode cannot call a per-id endpoint. |
| A command line tool | supported | [cli-wrapper-template](cli-wrapper-template) | `kit/examples/cli-wrapper-template/check.json` | Personal pack only; argument list, no shell; per-OS command table; 60 s at most; stderr is not seen. |
| A service on this computer (http_local) | supported | [local-service-template](local-service-template) | `toolkit/test/personal.test.mjs` | Loopback only, one GET or POST, no script, no secrets. Bolt reserves ports 13017 to 13027 and 15432 to 15441. |
| A local file the person names | supported | [file-insights-template](file-insights-template) | `kit/examples/file-insights-template/check.json` | Declare files; caps on size; a path cannot travel in a nav arg. |
| An MCP server | partial | snippet in ENGINE.md | `toolkit/test/cold-agent.test.mjs` | No native MCP runtime. A bridge script can call one tool over stdio; tested only against a stand-in server, not a real MCP server. |
| Keys from the keychain or a private file | supported | [portal-template](portal-template) | `kit/python/tests/test_secrets.py` | Lookup order: environment (terminal only), keychain, then a 0600 .env file. A shell variable does not reach the script under Bolt. |
| Keys stripped from API answers before cache | partial | [script-template](script-template) | `kit/python/tests/test_round2_security.py` | Strips the key (as written, URL-encoded, hex, base64, any letter case), user:password@ and credential-named query values, also inside nested, fragment and encoded links. Cannot strip: HTTP Basic base64 at another alignment, HTML entities, colon-separated hex, a split key, a key held as a JSON number, a value encoded twice. A key under 3 characters is refused. |
| Sample data: no key, no network | supported | [portal-template](portal-template) | `kit/python/tests/test_portal_engine.py` | Ship live (api.fixture_default false). Put "fixture": true at the top of check.json; an installed pack cannot be switched to sample data. |
| Several sources at once inside one deadline | supported | [system-glance](system-glance) | `kit/python/tests/test_probe.py` | Partial failure shows per-source rows; an unread value is never zero. |
| permissions block in the app file | partial | no example yet | `toolkit/test/cold-agent.test.mjs` | Declared and shown at install and compared with what the files use (permissions_differ). Bolt does not enforce it at run time. |
| Sandbox: a script confined to what it declares | not supported | none | `toolkit/test/docs-drift.test.mjs` | Not shipped. A personal script runs as you, with your files and network. Confinement is planned. Install only code you have read. |
| Windows | partial | see any example app file | `toolkit/test/kit.test.mjs` | Unproven: the command table accepts a windows entry and check can run fixtures labelled windows, but nothing has been run on Windows. |

## Snippets

### Pane: card (`widget.card`)

```
{"kind": "card", "mode": "selected_row", "bind": {"title": "{{row.name}}", "subtitle": "{{row.note}}", "actions": ["copy"]}}
```

### Pane: markdown (`widget.markdown`)

```
{"kind": "markdown", "mode": "selected_row", "bind": {"title": "{{row.title}}", "subtitle": "{{row.subtitle}}", "body": "{{row.body}}", "actions": ["copy"]}}
```

### Pane: entity_preview (`widget.entity_preview`)

```
{"kind": "entity_preview", "mode": "selected_row", "bind": {"title": "{{row.title}}"}}
```

### Pane: chart (`widget.chart`)

```
{"kind": "chart", "mode": "list_data", "bind": {"type": "bar", "x": "label", "y": "value", "label": "label"}}
```

### Pane: table (`widget.table`)

```
{"kind": "table", "mode": "list_data", "bind": {"sort": {"field": "commits", "dir": "desc"}, "totals_label": "Total"}}
```

### Pane: cards (`widget.cards`)

```
{"kind": "cards", "mode": "list_data", "bind": {"layout": "tiles"}}
```

### Pane: detail (`widget.detail`)

```
{"kind": "detail", "mode": "selected_row", "bind": {"title": "{{row.service}}"}}
```

### Pane: json_tree (`widget.json_tree`)

```
{"kind": "json_tree", "mode": "selected_row", "bind": {"source": "data"}}
```

### Pane: diff (`widget.diff`)

```
{"kind": "diff", "mode": "selected_row", "bind": {"left": "{{row.left}}", "right": "{{row.right}}"}}
```

### Pane: image_grid (`widget.image_grid`)

```
{"kind": "image_grid", "mode": "list_data", "bind": {"src": "{{row.src}}", "caption": "{{row.name}}", "columns": 3}}
```

### Left list: list, table, cards, detail (`layout.list_widget`)

```
presentation:
  widget: list
```

### Several views in one app (`layout.views`)

```
"views": [{"id": "tasks", "endpoint": "tasks"}]
```

### Drill from an overview row to a list (`nav.drill`)

```
{"title": "Open tickets", "view": "tickets", "arg": "open"}
```

### Back row on a drilled-in view (`nav.back`)

```
(automatic: the engine adds a Back row to every drilled-in view)
```

### Drill from a row to related rows of another view (`nav.children`)

```
"children": [{"view": "tasks", "match": "control_id"}]
```

### Row id from another field (id_field, parent_field) (`nav.id_field`)

```
{"id": "asteroids", "endpoint": "asteroids", "id_field": "neo_reference_id", "children": [{"view": "sameday", "match": "date", "parent_field": "date"}]}
```

### Filter a list by a typed word (`search.filter_word`)

```
=portal tickets urgent
```

### Launcher filters rows as you type (`search.searchable`)

```
"app": {"searchable": true}
```

### Fresh cache and a stale copy when the API fails (`cache.fresh_stale`)

```
"cache": {"ttl": 45, "stale_max": 86400}
```

### A detail pane that changes with the selected row (`pane.per_row`)

```
{"kind": "entity_preview", "mode": "selected_row"}
```

### Number tiles with a meter, unit, note and badge rules (`pane.tiles`)

```
"tile": {"label": "Open tickets", "value": "tickets_open", "max": "tickets_total", "badge": [{"if": "tickets_open>0", "badge": "ACTION"}, {"badge": "CLEAR"}]}
```

### Footer buttons (url, composer, utility) (`actions.footer`)

```
actions:
  - { id: copy, kind: composer, target: row, label: Copy, insert: "{{row.copy_text}}" }
```

### Run action: one click runs this app with a fixed query (`actions.run`)

```
actions:
  - { id: refresh, kind: run, label: Refresh, query_template: "overview refresh" }
```

### Footer button icon (`actions.icon`)

```
actions:
  - { id: open, kind: url, label: Open, icon: globe, url_template: "{{row.open_url}}" }
```

### Open a place in Maps from a row (instead of a map pane) (`actions.maps_link`)

```
"url": "https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"
```

### Row actions: Open and Copy from config (`actions.row`)

```
"url": "https://app.example.com/tickets/{id}"
```

### Icons in config.json and the app file (`icons.names`)

```
"icon": "globe"
```

### Typed input form with validation (`inputs.form`)

```
"form": {"inputs": [{"name": "amount", "type": "number", "label": "Amount", "required": true}]}
```

### Secret input field (`inputs.secret`)

```
(not used by any example; read the key with get_secret instead)
```

### REST list endpoint (`api.rest_list`)

```
"endpoints": {"tickets": {"path": "/v1/tickets", "map": {"title": "summary"}}}
```

### A list of ids, then one request per id (`api.id_hydrate`)

```
"news": {"path": "https://hacker-news.firebaseio.com/v0/topstories.json", "hydrate": {"path": "https://hacker-news.firebaseio.com/v0/item/{id}.json", "limit": 8}}
```

### API key sent as a query parameter (`api.query_key_auth`)

```
"api": {"auth_in": "query", "auth_param": "api_key"}
```

### API key sent in a header (`api.header_auth`)

```
"api": {"key_env": "EXAMPLE_API_KEY", "auth_header": "Authorization", "auth_prefix": "Bearer "}
```

### No key at all (`api.keyless`)

```
"api": {"base_url": "https://api.open-meteo.com", "fixture_default": false}
```

### Date tokens in a path: {today}, {today-7d}, {today+1d} (`api.date_tokens`)

```
"asteroids": {"path": "/neo/rest/v1/feed?start_date={today-2d}&end_date={today}"}
```

### An object of lists keyed by date or name (`api.object_keyed_lists`)

```
"asteroids": {"data": "near_earth_objects", "flatten": "date"}
```

### A second host for one endpoint (`api.second_host`)

```
"api": {"allowed_hosts": ["geocoding-api.open-meteo.com"]}
```

### Refuse an answer that lacks fields (`api.require`)

```
"require": ["current"]
```

### Chain endpoints: one answer feeds the next path (`api.chain`)

```
"lookup": {"steps": ["geocode", "weather"]}
```

### A command line tool (`api.cli`)

```
"commands": (see config.json)
```

### A service on this computer (http_local) (`api.local_http`)

```
http:
  port: 11434
  request: { method: GET, path: /api/tags }
  parse: json
```

### A local file the person names (`api.file`)

```
(path comes from the query word; see insights.py)
```

### An MCP server (`api.mcp`)

```
(see the MCP workaround script in ENGINE.md)
```

### Keys from the keychain or a private file (`secrets.private_key`)

```
"api": {"key_env": "EXAMPLE_API_KEY", "env_file": "~/.config/portal-template/.env"}
```

### Keys stripped from API answers before cache (`secrets.redaction`)

```
kit.redact_tree(answer, [key], auth_param)
```

### Sample data: no key, no network (`sample.mode`)

```
"api": {"fixture_default": false, "fixture_file": "fixtures.json"}
```

### Several sources at once inside one deadline (`parallel.sources`)

```
(kit.run_parallel in the script)
```

### permissions block in the app file (`permissions.block`)

```
permissions:
  network:
    - { host: api.example.com }
```

### Windows (`platform.windows`)

```
"windows": "python {{scripts_dir}}/engine.py {{view}} {{arg}}"
```
