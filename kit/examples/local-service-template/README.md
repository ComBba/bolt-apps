# local-service-template

## What this teaches
`runtime: http_local`: an app with no script at all. Bolt makes one GET request to a service listening on this computer, reads the JSON, and shows one row per item. This example reads the model list of an Ollama server (`/api/tags`, key `models`) on port 11434 and shows name, size, modified time and digest.

## What the schema allows (read from `schema/user-app.schema.json` and the launcher source, 2026-11-15)
- `http.port` (1 to 65535), `http.host` only `localhost`, the IPv4 loopback address or `::1`: the app cannot name another machine.
- `http.request`: `method` GET or POST, and a `path` (query-word values are percent-encoded into it, never run).
- `http.parse`: `json`, `lines` or `raw`; `rows_path` picks the list inside a JSON object; `timeout_seconds` 1 to 60; `headers` (no secrets).
- No script, no shell. The pack carries one YAML file. Bolt shows "talk to a service on this computer (port N)" before installing.
- Not possible: a service on another host, a key kept in the keychain, retries, several requests, caching, a second call that depends on the first. For those use a `bridge` script (see `../repo-radar`).
- Bolt ships its own `=ollama` and `=docker` apps this way. This example uses the chip `localmodels` so it does not clash.

## Honest status
Not run in Bolt and not run against a real Ollama: there is none on this computer. The response shape (`models[].name`, `model`, `size`, `modified_at`, `digest`) is from Ollama's API documentation and Bolt's own `=ollama` manifest, not a recording. Passes `lint --personal`; `check` does not apply to an app with no script. If the service is not running Bolt shows its own "could not connect" row.

## Copy this to build
An app over any loopback HTTP service: Docker Engine on `2375`, a dev server's status endpoint, a database admin API, a local LLM server. Change `port`, `request.path`, `rows_path`, the title and subtitle fields and the detail pane.

## Edit only these fields
`utilities/localmodels.yaml`: `chip`, `title`, `http.port`, `http.request.path`, `http.rows_path`, `presentation.title_field`, `presentation.subtitle_field`, `presentation.right_widget.bind.fields`.

## Commands
Run `./bolt-apps keygen` once before the first pack: it makes your signing key and never overwrites one.
```
./bolt-apps lint kit/examples/local-service-template --personal
./bolt-apps pack kit/examples/local-service-template --personal --version 1.0.1 --out local-service-template-1.0.1.boltpack
```
