# Where `bolt-apps verify` gets its rules

`schema/install-rules.json` holds the install rules Bolt enforces on a pack-installed User App, as data: the allowed runtimes, action kinds, `emits` kinds, widgets, parse modes, the top-level keys Bolt accepts, the admin-only keys it refuses, the shell characters it forbids in a command, the pack limits and which entry kinds the launcher drop installs. `conformance/verify-cases.json` holds cases that edit a known-good app and name the finding `verify` must report. For the YAML rules each case also carries `bolt_error_contains`, the text Bolt's own parser puts in the load error.

The source of truth is the launcher's own manifest contract, pack validation, pack installer and signature verifier. The data file is a mirror, read on 2026-11-01.

## What `verify` does not do

It reads YAML with plain text rules, not Bolt's parser. It does not check `presentation` fields, `inputs`, `transform.pipe` steps, `recognize` regexes, reserved ports, env-variable rules or the schema of the rows a script prints (use `check` for that). A pass means none of the known ways to fail were found.

## Keeping Bolt and this repo equal

Today nothing in Bolt reads these two files, so they can drift. The fix needs a launcher change, so it is a proposal:

1. The launcher's manifest contract gets a test that loads `schema/install-rules.json` (vendored into its test data with a sha256 pin) and asserts each list equals the launcher's own constant: `ALLOWED_RUNTIME`, `ALLOWED_ACTION_KIND`, `ALLOWED_EMITS`, `ALLOWED_WIDGET`, `ALLOWED_PARSE`, `ALLOWED_HTTP_LOCAL_HOSTS`, `ALLOWED_HTTP_METHOD`, `FORBIDDEN_SHELL_CHARS`, `MAX_SCHEMA_VERSION`, the top-level field names of `UserUtilityContract`, `MAX_PACK_ENTRIES`, `MAX_UNPACKED_BYTES`.
2. The same test builds each case of `conformance/verify-cases.json` and runs the YAML through the launcher's pack manifest parser: a case with `bolt_error_contains` must return `Err` containing that text, a case with no `expect` must return `Ok`.
3. This repo's CI already runs the same cases through `verify`, so a change on either side that breaks the other fails a test.

Files on the launcher side: the contract's test module and two vendored test data files, one for the rules and one for the verify cases. The site's rule pages should be generated from `schema/install-rules.json` rather than typed by hand.
