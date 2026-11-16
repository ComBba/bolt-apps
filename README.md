# Bolt Apps

> **Apps built before this change:** remove the old app in Bolt (Settings, Desktop, User Apps; the Remove button is on the app's row on 181, and newer builds also show it in the expanded panel; do not delete files by hand), run `./bolt-apps new <template> <id>`, copy your own `config.json` and `fixtures.json` over the new ones, re-run `./bolt-apps check`, then `./bolt-apps ship`.

Small things people add to [Bolt](https://sparcle.app/bolt/) to do their job faster: a
snippet that cleans a list, a search prefix for a site you use every day, a launcher key
that turns pasted CSV into a Markdown table.

> **The gallery is closed.** You can read everything here, use the toolkit and build apps for yourself today.
>
> **The gallery is not open yet.**
> This repository will become the community gallery of Bolt Apps. It opens only when
> Bolt enforces each app's declared permissions at run time and shows them in plain
> words when you install it, and when the rules and docs here are final. Until then,
> contributions are not accepted and pull requests from outside Sparcle are closed.

## What a Bolt App is

Bolt Apps extend what Bolt can do. Start with a snippet or a search prefix. Add a YAML file that
reshapes or recognizes what you paste. For your own use you can also add a command or script that
returns rows (the [toolkit](toolkit/README.md) packs it with `--personal`); the gallery takes tier 1
and 2 apps only, so that kind stays yours. Skills and agents import from Settings, Agents, Import.
Connectors, detectors and compliance packs are for company admins. Every app has a safety tier, so
you know what it can reach before you add it.

In this repository:

A Bolt App is a folder under [`apps/`](apps/) holding one or more of the things Bolt can
load, plus a `bolt-app.json` that describes it and carries its tests. It can be packed
into a **Boltpack** (`.boltpack`), the signed file Bolt installs.

| What an app can hold | Folder | What it does |
|---|---|---|
| Snippet | `snippets/` | Text you type as `;key`, with fill-in fields and filters |
| Search engine | `search_engines/` | A prefix that searches a site |
| User App | `utilities/` | A launcher `=key` that reshapes what you paste (`runtime: transform`) |

Bolt supports more kinds than these (skills, agents, connectors, detectors, compliance
packs). The gallery starts with the three above. See
[Extend Bolt](https://sparcle.app/docs/extend/) for everything Bolt can load today.

## Safety tiers

Every app has a tier. The checker works it out from the content and refuses an app that
claims a lower one.

| Tier | Means | In this gallery |
|---|---|---|
| 1 | **Data only.** Text and links: snippets, search engines. | Accepted after the check and a quick human look |
| 2 | **Acts inside Bolt** on what you paste or type, with the permissions it declares shown when you add it. No commands, no network. | Accepted after the check and a quick human look |
| 3 | **Touches your system or the network.** Runs commands, reads files, calls outside services, gives an AI agent tools. | Only when **Reviewed by Sparcle**, or approved inside your own company. Never accepted from the community without that review. |

**Reviewed by Sparcle** means Sparcle checked this version's declared permissions and
behaviour. It is not a guarantee.

A company's device settings always win over any app. An admin can allow only approved
apps.

## Installing an app

When the gallery opens, you will add an app from Bolt or from
[sparcle.app](https://sparcle.app/docs/extend/gallery/). Until then you can copy an app by
hand:

- **Snippet:** Settings, Search & Commands, Snippets, Add snippet; paste the `content`.
- **Search engine:** Settings, Search & Commands, Search Engines, Add engine.
- **User App:** Settings, Desktop App, User Apps, Open folder; save the `.yaml` there and
  click Reload.

## Toolkit: build your own

The [`toolkit/`](toolkit/) folder holds `bolt-apps`, a small command that scaffolds an app from a
working template, lints it, signs it and packs it into a `.boltpack` you can drop on Bolt. No
account and no dependencies; see [toolkit/README.md](toolkit/README.md).

```
node toolkit/bin/bolt-apps.mjs new my-app --type transform
node toolkit/bin/bolt-apps.mjs lint apps/my-app
node toolkit/bin/bolt-apps.mjs keygen
node toolkit/bin/bolt-apps.mjs pack apps/my-app
```

For apps that run a script (not accepted in the gallery), the [authoring kit](kit/) and its [design](docs/kit-design.md) take care of formatting, row structure and JSON output.

### A rich app for a web API, in minutes

Want tiles, drill down with Back, a detail panel, a cache and plain error rows for a web API? Copy
[`kit/examples/portal-template`](kit/examples/portal-template), make a copy with `bolt-apps new` (it renames every file for your app; pick a distinctive app id, since two authors who both ship `weather` still collide), change data in
`scripts/my-app__config.json` and `scripts/my-app__fixtures.json`, generate the YAML, then check and pack it for yourself:

```
node <this repo>/toolkit/bin/bolt-apps.mjs new portal-template my-app --dir ~ && cd ~/my-app      # folder name = app id
# edit scripts/my-app__config.json and scripts/my-app__fixtures.json
python3 scripts/my-app__engine.py --emit-yaml > utilities/my-app.yaml
node <this repo>/toolkit/bin/bolt-apps.mjs check .
node <this repo>/toolkit/bin/bolt-apps.mjs pack . --personal --version 1.0.1 --out ../my-app-1.0.1.boltpack
```

Drop the `.boltpack` on the Bolt launcher or Bolt Apps; Bolt shows what it can do and asks you to
confirm (it rates a personal app high risk, which is expected). Raise `--version` each time you pack
again: Bolt refuses a pack that is not newer than the installed one, and a repack must use the same signing key. Keep packs outside the app folder. This personal pack is how a rich app ships: it runs a script and calls the network (tier 3), so the gallery does not take it.
[`kit/examples/acme-dash`](kit/examples/acme-dash) shows the same template with 8 views and three levels.
Walkthrough with the row formats: <https://sparcle.app/docs/extend/rich-apps/>. Agents: [AGENTS.md](AGENTS.md) section 4c.

## Contributing

Not open yet (see the note at the top). When it opens:

1. Build the app in Bolt with made-up data.
2. Run `bolt-apps check` on its folder ([CHECKER.md](CHECKER.md)).
3. Open a pull request using the template, with every commit signed off.

Read [CONTRIBUTING.md](CONTRIBUTING.md) if you are a person and [AGENTS.md](AGENTS.md) if
you are an AI coding agent.

## Credit for authors

Authors get recognition, not money:

- your name and link on the app's card and on Bolt's install screen;
- an author profile with the apps you made;
- badges, such as first app, Reviewed by Sparcle, and community favourite;
- an "added N times" count;
- a monthly spotlight, only if you tick the consent box in your pull request.

Thumbs-up reactions and counts are recognition only. Nothing depends on them.

## Community

- **Vote** with a thumbs-up on an app's pull request or its tracking issue.
- **Talk** in GitHub Discussions: Ideas, Show and tell, Q&A, Reviews.
- **Ranking:** [`RANKING.md`](RANKING.md) and [`INDEX.json`](INDEX.json) are generated by a
  workflow from reactions and gallery fetch counts. They hold no personal data and decide
  nothing.

## Security

Do not report a security problem in a public issue. See [SECURITY.md](SECURITY.md).

## Licence

[Apache License 2.0](LICENSE). Contributions are accepted under the same licence, with a
[Developer Certificate of Origin](https://developercertificate.org/) sign-off on every
commit; see [CONTRIBUTING.md](CONTRIBUTING.md).
