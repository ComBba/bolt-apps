# around

## What this teaches
Stitching independent systems on coordinates. `=around Bryant Park, New York` geocodes the place, then calls four more APIs in parallel and joins everything by haversine distance into one verdict, per-row panels and Open in Maps actions.

| View | Pane | What it shows |
|---|---|---|
| overview | cards (tiles) | verdict, five source health badges, cafes and gyms, nearest bike dock (live), weather sparkline, landmarks |
| places | detail | per cafe or gym: distance and walk time, hours, brand or independent, nearest bike dock, weather there, source |
| bikes | table | nearest docks: bikes, free slots, distance, "updated N s ago" |
| weather | line chart | temperature for the next 12 hours (rain chance in each row) |
| landmarks | detail | Wikipedia articles within 1 km |
| keys | detail | the auth matrix demo |

6 views including the overview.

## Live terms, checked 2026-11-15 with real requests
| Source | Auth | Terms and limits | Seen |
|---|---|---|---|
| Nominatim `nominatim.openstreetmap.org` | none | Usage policy: at most 1 request a second, a User-Agent that names the app (a request with none got HTTP 403), show attribution, no search-as-you-type, no periodic bulk use. | This app sends one geocode per new place, waits 1.1 s from the last one, and keeps the answer 30 days. |
| Overpass `overpass-api.de` | none | Public servers share their capacity; they answer 502 or 504 when busy. | It answered 502 "at capacity" for several minutes, and the call that worked took 32 to 34 s. The app keeps places 1 hour, shows an old copy when it fails, and the other rows still show. A live run can show "Places down": that is real, not a bug. |
| CityBikes `api.citybik.es/v2` | none | Free, no key. | The network answer is large, so only stations within 1.5 km are used. The network is chosen from a short table in `config.json` (`bike_networks`, every id checked to exist); a place with no network within 40 km says "none nearby". |
| Open-Meteo `api.open-meteo.com` | none | Free for non-commercial use, credit Open-Meteo (CC BY 4.0). `X-RateLimit-Limit: 600` a minute. | |
| Wikipedia geosearch `en.wikipedia.org/w/api.php` | none | A descriptive User-Agent is expected. Content CC BY-SA. | |
| OpenTripMap `api.opentripmap.com` | free key, required | Answers 401 without a key. Used only by the keys demo; no request is made without a key. | |

Attribution shown in the app: map data (c) OpenStreetMap contributors (ODbL), Open-Meteo, Wikipedia, CityBikes.

## TTLs and "live"
Bikes 30 s, places 1 h, weather 15 min, Wikipedia 1 day, geocode 30 days (`sources` in `config.json`). Bolt refreshes only when you press Enter, so "live" means as fresh as the last Enter. The bike rows show "updated N s ago", counted from the station's own timestamp, so a cached answer shows its true age. Each source falls back to a copy up to 7 days old with an "old copy" badge; a failed call is never cached.

## The auth matrix (keys view)
| Mode | What the app does |
|---|---|
| no key | sends nothing (the four main sources) |
| optional key | would send `Authorization: Bearer ...` and works without it |
| required free key | OpenTripMap: with no key the view shows an "Add your free key" setup row with the exact one-line command from `kit.setup_hint`; the key goes in the `apikey` query value |
| bearer | `Authorization: Bearer ...` |
| basic | `Authorization: Basic ...` built from `user:password` |

`build_auth()` makes the headers; only a masked form is ever shown (`********`). Keys are read with `kit.get_secret` (keychain, then `~/.config/around/.env` mode 0600), never from a shell variable, which does not reach the script under Bolt. The bearer, basic and optional rows are a pattern demo: no real service is called with them. Add `demo-secrets` to the query to see fake secrets built into requests and masked. Not built: the attractions call itself (the key is verified to be required; I had no key to record a real answer).

## Sample data
The app ships live (`api.fixture_default` is false); `check` runs it in sample mode (`"fixture": true` in `check.json`) on real answers recorded 2026-11-15 for "Bryant Park, New York" (trimmed), clock fixed at the recording time. `attractions_sample` in `fixtures.json` is hand-written and unused. Any place works in the live app; set `api.fixture_default` to true only to demo sample mode. Failure previews: add `demo-places-down`, `demo-bikes-down`, `demo-weather-down` or `demo-wiki-down`.

## Copy this to build
Any app that joins sources with no shared id except location or time: a trip planner, a store finder, an event briefing. Replace the calls in `gather()`, the `n_*` readers, `stitch()` and `verdict()`.

## Edit only these fields
`scripts/around__config.json`: `categories` (OSM filters), `bike_networks`, `radius_m`, `sources`, `score` (weights, comfort range, verdict labels), `auth_demo`, `api`. `scripts/around__fixtures.json`: recorded answers.

## Commands
Run `./bolt-apps keygen` once before the first pack: it makes your signing key and never overwrites one.
```
./bolt-apps kit vendor --flat kit/examples/around
python3 kit/examples/around/scripts/around__around.py --emit-yaml > kit/examples/around/utilities/around.yaml
./bolt-apps check kit/examples/around --update-golden
./bolt-apps lint kit/examples/around --personal
./bolt-apps pack kit/examples/around --personal --version 1.0.1 --out around-1.0.1.boltpack
```
Use: `=around Bryant Park, New York`. A map pane is not used: personal apps cannot show the map widget, so each row carries an Open in Maps action (OpenStreetMap).

## Not covered
Only English Wikipedia. Opening hours are shown as OpenStreetMap writes them, not evaluated against the clock. The weather is for the searched point, not each place. Not run in the real launcher or on Windows.
