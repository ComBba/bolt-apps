# cli-wrapper-template

## What this teaches
How to wrap a command-line tool as a Bolt App, using the system `ping` as the tool. One typed host name in, a verdict out (UP, LOSSY, SLOW, DOWN), tiles with a round-trip sparkline, a titled line chart of each reply, the raw output and the exact command that ran.

| Technique | Where |
|---|---|
| A command table per OS | `config.json` `commands` (macOS and Linux differ: `-t` against `-w`) |
| Arguments that cannot add a command | the command runs as an argument list with no shell; the host must match `host.pattern` (no leading dash, no `;`, `$(...)`, spaces or quotes); the count must be a whole number in range |
| Timeouts | `limits.command_timeout` caps the run; a hung command is killed with its children and shown as "ping timed out", and is never cached |
| Output parsing | regular expressions per OS in `config.json` `parse`; a number that is not in the output is unknown, never 0 |
| Exit codes | `exit_codes` per OS: 68 on macOS and 2 on Linux mean the name did not resolve; 2 on macOS and 1 on Linux mean no reply (an answer, not a failure) |
| Tool missing, tool failing | one plain row each, with the install hint from `tool.install_hint` |
| Result reuse | a result is kept `limits.result_ttl` seconds so opening Replies or Raw output does not ping again; "Ping again" bypasses it |
| Fixture-recorded output | `fixtures/<os>/*.out` are the command's output; the checker puts a stub `ping` that prints them first on the path |

## What was recorded and what was not (2026-11-15)
- `fixtures/macos/ping.out` and `loss.out` are real output of `/sbin/ping` on macOS (`ping -c 3 -t 5 one.one.one.one`, and three probes to the documentation address 192.0.2.1, which never answers).
- `fixtures/macos/partial-edited.out` is the recorded success output hand-edited: one reply line removed and the counts and summary changed to match. It exists to test partial loss. It is not a recording.
- `fixtures/linux/ping.out` was NOT recorded on Linux. It follows the iputils ping format from its manual page, with the numbers of the macOS recording. The Linux column of `commands` and `parse` is therefore tested against a format fixture only, not on a Linux computer.
- Unknown host is tested with exit 68 and empty output, which is what the kit sees: the launcher runner reads the command's output only, not its error text.
- Windows is not supported (the checker refuses it in plain words). To add it, add a `commands.windows` entry (`ping -n {count} -w {wait_ms} {host}`) and `parse.windows`, then record real output on Windows.

## Copy this to build
An app around any read-only command: `dig`, `whois`, `git log`, `df`, `docker ps`. Change `tool`, `commands`, `exit_codes` and `parse`, then change `build()` rows to the shape of your tool's output. Keep `check_host` style validation for every typed word, and never build a command string.

## Edit only these fields
For a CLI app you ARE expected to edit `scripts/wrap.py`: replace `build()` with rows that fit what your tool prints, and `parse_output()` if the output is not ping's. The rest is data in `scripts/config.json`: `app` (id, chip, title, icon `network` is a valid launcher icon), `tool`, `params`, `host`, `commands`, `exit_codes`, `limits`, `parse`, `verdict`, `chart`.

`scripts/fixtures.json` is a sample output per system. Sample mode (`BOLT_APP_FIXTURE=1`, or `"fixture": true` in `check.json`) parses it instead of running the tool, so a copy has a working path before the tool is installed. The bridge command names `config.json`, `fixtures.json` and `bolt_app_kit.py` as helper files, and `split_args()` drops those trailing words, so keep all three in the command if you rename or add helpers. The check stubs in `fixtures/<os>/*.out` are for the checker only and are not packed. A tool with several subcommands is tested with `by_args` stubs (see `../ENGINE.md`).

## Commands
Run `./bolt-apps keygen` once before the first pack: it makes your signing key and never overwrites one.
```
./bolt-apps kit vendor --flat kit/examples/cli-wrapper-template
python3 kit/examples/cli-wrapper-template/scripts/wrap.py --emit-yaml > kit/examples/cli-wrapper-template/utilities/pingcheck.yaml
./bolt-apps check kit/examples/cli-wrapper-template --update-golden
./bolt-apps lint kit/examples/cli-wrapper-template --personal
./bolt-apps pack kit/examples/cli-wrapper-template --personal --version 1.0.1 --out cli-wrapper-template-1.0.1.boltpack
```
Use: `=pingcheck one.one.one.one`, `=pingcheck example.com 5` (count 1 to 10), then the Replies, Raw output and The command rows.

## Not covered
Ping to a host that blocks ICMP looks like DOWN. IPv6-only hosts need `ping6` on some systems. Only the first four words of a typed query are read.
