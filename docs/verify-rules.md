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

## Bolt said X, do Y

Every refusal Bolt's installer and loader can give a personal pack, with the fix in plain words. `bolt-apps ship` prints the common ones and `bolt-apps doctor --bolt-says` prints all of them. A test keeps this table equal to the one in the toolkit.

| Bolt says | Code | What to do |
|---|---|---|
| version X is already installed, and a pack is only replaced by a newer version | `same_or_older_version` | Run bolt-apps ship again: it picks a higher version by itself. If you passed --version, use a higher number than the one installed. |
| it cannot tell whether this is newer than the installed version | `version_unreadable` | A version is numbers with dots, such as 1.0.5. Run bolt-apps ship without --version. |
| a script file already belongs to another app | `owned_by_other` | Two apps use the same script file name. Rebuild with the current bolt-apps: every file is named <app id>__<name>. Or remove the other app first. |
| a file is already there and no pack installed it | `file_exists` | A file with that name in your scripts folder was added by hand or came with Bolt. Open it (Settings, Desktop, User Apps, Open folder) and delete it, or rename yours. |
| a name is both a file and a folder | `file_and_folder` | Rename the file or the folder inside scripts/ so one name is not both. |
| two names differ only in letter case | `case_collision` | Rename one of the two files: macOS and Windows treat them as one file. |
| a script is nested more than 8 folders deep | `too_deep` | Keep scripts flat, directly in scripts/ (bolt-apps new does this). |
| a script path is not safe | `unsafe_path` | Remove . or .. or odd characters from the script name; use letters, digits, . _ and -. |
| a script cannot be placed because something else is in its way in your scripts folder | `in_the_way` | Open your folder (Settings, Desktop, User Apps, Open folder) and remove the file, folder or link that has the same name. |
| a file named scripts is in your user apps folder | `scripts_is_a_file` | Move that file away from your user apps folder, then drop the pack again. |
| it could not write a file | `write_failed` | Free some disk space or check you can write to your Bolt folder, then drop the pack again. |
| its list of installed packs could not be read | `ledger_unreadable` | Do not delete anything. Ask for help with the file .boltpack-installs.json in your user apps folder. |
| it could not confirm the pack's signature a second time | `signature_recheck` | Build the pack again with bolt-apps ship and drop the new file; do not copy a pack between folders while Bolt reads it. |
| a file does not match the pack's signed listing / pack rejected | `unverified` | The pack was changed or damaged after signing. Run bolt-apps ship again and drop the new file; never edit a .boltpack. |
| it lists a file outside the pack | `outside_pack` | Build the pack with bolt-apps ship, not by hand. |
| Install cancelled: the pack is signed by its author, not by a key built into Bolt | `cancelled` | You chose Cancel, or did not approve the second prompt. Drop the pack again and approve both prompts if you trust the app. |
| Your organization's policy on this device installs only packs signed with a key built into Bolt | `org_policy` | A company policy blocks personal apps on this computer. Nothing is wrong with the app; ask your admin, or use a computer without that policy. |
| Not loaded: this app's files do not match the signed pack Bolt recorded for it | `not_loaded_changed` | A script was edited after install. Run bolt-apps ship again and drop the new pack; it replaces the changed files. |
| this app's command names a file in Bolt's scripts folder directly | `scripts_direct` | Write every script as {{scripts_dir}}/<app id>__<file> in the app file, never a full path. bolt-apps lint --personal shows the line. |
| the app names its scripts in a form Bolt cannot resolve to one file each / is missing / is a link / is too large to check | `cannot_check` | Name each script once as {{scripts_dir}}/<app id>__<file>, keep each under 2 MB, no links, and make sure the file is in scripts/. bolt-apps verify names the file. |
| pack rejected: it unpacks to more than 64 MB / holds more than 1024 files / the file is over 50 MB | `pack_too_big` | An app is small text and scripts. Remove big files from the app folder. |
| pack rejected: the archive cannot be read | `pack_unreadable` | The file is not a .boltpack or is damaged. Run bolt-apps ship again and drop the new file. |
| pack rejected: a file is not a valid app | `not_valid_app` | Run bolt-apps verify on the app folder: it names the line in the app file to fix. |

### The exact words Bolt 0.1.181 uses

`<name>`, `<new>`, `<old>`, `<file>` and `<other app>` stand for what Bolt fills in.

| Code | Bolt's sentence |
|---|---|
| `same_or_older_version` | Bolt did not install `<name>` `<new>`: version `<old>` is already installed, and a pack is only replaced by a newer version. To go back to an older version, remove the installed apps first. |
| `version_unreadable` | Bolt did not install `<name>` `<new>`: it cannot tell whether this is newer than the installed version `<old>`. Remove the installed apps first to install this version. |
| `owned_by_other` | Bolt did not install `<name>`: `<file>` already belongs to `<other app>`. Remove that app first if you want this one instead. |
| `too_deep` | Bolt did not install `<name>`: `<file>` is nested more than 8 folders deep. Ask the pack's author to use fewer folders. |
| `org_policy` | Your organization's policy on this device installs only packs signed with a key built into Bolt (...). `<name>` is signed only by its author, so Bolt did not install it. ... Ask your IT team if you need it. |

Name lengths: Bolt accepts up to 128 characters per file or folder name and 512 for a whole path, and an app id is up to 64 characters. Every script starts with `<app id>__`, so `<app id>__<name>` must fit in 128. This toolkit packs a script name of at most 82 characters, because it writes the path `manifests/scripts/<name>` into a 100-character field.

