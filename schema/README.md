# Schemas

This folder is the one source for every schema and rules file. The website copies these files at build time (`scripts/sync-bolt-apps.sh` in the site repo); never edit a copy there.

| File | Describes | Public URL (the `$id`) |
|---|---|---|
| `user-app.schema.json` | the YAML app file, `utilities/<id>.yaml` | https://sparcle.app/schemas/user-app-v1.json |
| `bolt-app.schema.json` | the listing, `bolt-app.json` | https://sparcle.app/schemas/bolt-app-v1.json |
| `boltpack-manifest.schema.json` | `bundle.json` inside a `.boltpack` | https://sparcle.app/schemas/boltpack-bundle-v1.json |
| `connector.schema.json` | a company-admin connector manifest (not for apps here) | https://sparcle.app/schemas/connector-v1.json |
| `bolt-rules.json` | limits and lists the toolkit, kit, schema and docs all read | https://sparcle.app/schemas/bolt-rules.json |
| `install-rules.json` | install rules `verify` mirrors | https://sparcle.app/schemas/install-rules.json |

The old address https://sparcle.app/bolt-app.schema.json redirects to the YAML app schema.

Rules for changing them:

- A limit or a list (widget kinds, footer buttons, label length, rows, env names) is written in `bolt-rules.json` only. The schema mirrors it and `toolkit/test/schema-agree.test.mjs` fails when they differ.
- A schema describes the shape. Bolt refuses what breaks a rule, including rules a schema cannot say.
- `permissions` in an app file is declared and shown at install. Bolt does not enforce it at run time yet.
