# Privacy of this repository

This note covers the code in this repository: the `bolt-apps` toolkit, the Python kit and
engine, and the example apps. The company policy for the Bolt app and sparcle.app is at
<https://sparcle.app/privacy/>. This note does not change it. If they ever differ, the company
policy is the one to read, and please tell us at privacy@sparcle.app.

## What this repository collects

Nothing. The toolkit has no telemetry, no analytics, no account and no update check. It does
not send anything to Sparcle.

## When the toolkit uses the network

The toolkit itself makes no network call. It was read for this on 2026-11-17: the code
under `toolkit/bin` and `toolkit/lib` does not open a connection. The only outside program it
starts is `git`, and only to read local facts.

| Command | Network | What it does |
|---|---|---|
| `new`, `lint`, `pack`, `verify`, `keygen`, `kit`, `doctor` | none | Read and write files on your computer. |
| The stale-clone note (shown by `new` and `ship`) | none | Reads your clone's own git data (`git rev-list`, the age of `.git/FETCH_HEAD`). It does not run `git fetch`. |
| `check` | none by the toolkit | Runs an app's script against fixtures on your computer. The script is code you chose to run: read it first. |
| `run --sample` | none by the toolkit | Runs the app's script with sample data. |
| `run --live`, or `run` on an app whose default is live | whatever that app calls | Runs the app's script with your real home folder. An example app then contacts the services in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md), and your IP address and your search words go to them. |

## What is written on your computer

- `~/.bolt-apps/key.pem`: your signing key, made by `keygen` or the first `ship`, mode 600. It
  never leaves your computer. Keep it out of any repository.
- `~/.bolt-apps/packs/`: the `.boltpack` files `ship` makes, and `~/.bolt-apps/ship.json`, the
  version numbers it used.
- `~/.bolt-apps/cache/<app id>/`: answers an example app's script cached for a few minutes or
  hours (the kit's cache, `kit/python/bolt_app_kit/cache.py`), so it asks a service less often.
  You can delete this folder at any time.
- The app folders you make with `new`.

## Example apps and Bolt

This repository does not run apps. Bolt does, on your own device, after you install a pack.
When you run an example that calls a web service, your device contacts that service directly.
Sparcle does not receive those requests or their answers (the example scripts have no Sparcle
address in them besides a user-agent text that names this repository). The service sees your IP
address and what you asked for, and applies its own policy. What Bolt itself sends, if anything,
is described in the company policy above.

## GitHub

This repository is hosted on GitHub. GitHub's privacy statement applies when you open issues,
discussions or pull requests here. Do not put real personal data in any of them (see
[CONTRIBUTING.md](CONTRIBUTING.md)).

## Contact

Privacy questions: privacy@sparcle.app. Security problems: see [SECURITY.md](SECURITY.md).
