# repo-radar

## What this teaches
Joining several remote APIs into one verdict. `=repo-radar owner/repo` calls GitHub, npm, OSV.dev and Hacker News in parallel (a thread pool, a per-call timeout and one overall deadline), joins them on the repository and its npm package, scores 0 to 100, and shows what changed since you last looked.

| View | Pane | What it shows |
|---|---|---|
| overview | cards (tiles) | verdict, source health badges, stars, issues, releases, downloads, vulnerabilities, discussion |
| releases | diff | each release's notes against the one before (real multi-line text; the diff pane is unverified for rows in 181) |
| vulns | detail | each advisory: severity, open or fixed, fixed-in version, link to osv.dev |
| downloads | line chart | daily npm downloads, last 30 days |
| discussion | detail | Hacker News threads that link to the repo |
| since | detail | what changed against the copy saved on your computer: Before, After, Change (signed, with a percent), What it is |
| compare | table | `a/b vs c/d` side by side, leader per metric |

That is 7 views including the overview, under the launcher limit of 8.

## Live terms, checked 2026-11-15 with real requests
| Source | Auth | Limit | Notes |
|---|---|---|---|
| GitHub REST `api.github.com` | none; optional token | 60 requests an hour without a token (`x-ratelimit-limit: 60` seen), 5,000 with one | A `User-Agent` is required: a request without one got HTTP 403. This app uses 2 calls per repo, so about 30 lookups an hour without a token. The badge shows `remaining/limit` from the response headers. |
| npm registry `registry.npmjs.org` and downloads `api.npmjs.org` | none | no rate limit stated in the npm registry docs I could read; none seen in headers | Downloads: ranges up to 18 months, bulk up to 128 packages (not used). The registry answer is cached by the CDN for 5 minutes. |
| OSV.dev `api.osv.dev` | none | the OSV docs say "Currently there are no limits on the API" | POST `/v1/query` with a package name and, for the latest version, a version. |
| Hacker News search `hn.algolia.com/api/v1` | none | Algolia documents a per-IP hourly limit; its API page is client-rendered, so I could not read the number and did not rely on it. No limit headers seen. | Searching the url field for `github.com/owner/repo`. |

No source forbids this use: every call is a read of public data made when a person presses Enter, cached per source, and sent with a `User-Agent` that names the app. If a source changes its terms, change `hosts`, `sources` and the call list in `radar.py`.

## How the join works
- The npm package is guessed from the repo name, or given as `owner/repo:package`. It is used only if the package's `repository` field names the same GitHub repo. A package that points elsewhere, or names nothing, is shown as "not used" and so are its downloads and its OSV results. A name match is not an identity.
- OSV runs after npm, on the checked package: all known advisories, and the ones that affect the latest version (those count as open).
- The verdict weights (`weights`) and thresholds (`scoring`, `verdict`) are in `config.json`. A component whose source did not answer is left out and the other weights are re-scaled; the row then says "not scored: ..." and the badge is PARTIAL. It is never scored as zero or as clean.

## Failure behaviour
Each call is cached fresh for its source TTL (GitHub 10 min, npm 1 h, OSV 6 h, HN 30 min). If a call fails, an older copy up to 7 days old is shown with an "old copy" badge and its age. With no copy the row says unavailable, the badge says down, and the rest still shows. A rate limit shows an optional token row, not an error. A failed call is never cached.

## Optional GitHub token
Read with `kit.get_secret("repo-radar", "GITHUB_TOKEN")`: keychain first, then `~/.config/repo-radar/.env` (mode 0600). A shell variable never reaches the script under Bolt. The token is sent to `api.github.com` only and never shown. The row that offers it carries the exact one-line setup.

## Since you last looked
The newest result is saved in the kit cache (`~/.bolt-apps/cache/repo-radar/seen`). A run compares against the saved copy that is at least 60 minutes old (`snapshot_min_age_s`), so two runs a minute apart do not erase the change list. The first look at a repo says so.

## Sample data
The app ships live (`api.fixture_default` is false); `check` runs sample mode (`"fixture": true` in `check.json`) on answers recorded on 2026-11-15 for `expressjs/express` and `fastify/fastify` (trimmed), with the clock fixed at the recording time. The `seen` entry in `fixtures.json` is NOT recorded: it is a hand-edited earlier snapshot, with a made-up advisory id, so the Since view has something to show. Record more repos with `BOLT_APP_FIXTURE=0 python3 scripts/repo-radar__radar.py --record owner/repo`. Failure previews: add `demo-osv-down`, `demo-github-limit`, `demo-npm-none` or `demo-hn-down` to the query in sample mode.

## Copy this to build
Any app that stitches two or more APIs on a shared key: a company lookup, a package audit, a city briefing. Replace the call table in `urls()`, the `n_*` functions that read each answer, the join in `model()` and the score.

## Edit only these fields
`scripts/repo-radar__config.json`: `hosts`, `sources` (labels and TTLs), `weights`, `scoring`, `verdict`, `api` (timeouts, workers), `charts`. `scripts/repo-radar__fixtures.json`: recorded answers.

## Commands
Run `./bolt-apps keygen` once before the first pack: it makes your signing key and never overwrites one.
```
./bolt-apps kit vendor --flat kit/examples/repo-radar
python3 kit/examples/repo-radar/scripts/repo-radar__radar.py --emit-yaml > kit/examples/repo-radar/utilities/radar.yaml
./bolt-apps check kit/examples/repo-radar --update-golden
./bolt-apps lint kit/examples/repo-radar --personal
./bolt-apps pack kit/examples/repo-radar --personal --version 1.0.1 --out repo-radar-1.0.1.boltpack
```
Use: `=repo-radar expressjs/express`, `=repo-radar fastify/fastify vs expressjs/express`, `=repo-radar owner/repo:npm-name`.

## Not covered
Only npm packages (OSV supports other ecosystems). Not run in the real launcher. Windows was not tested. A repo with more than 8 releases shows the newest 8. The Hacker News total counts stories that link to the repo, not mentions in comments.
