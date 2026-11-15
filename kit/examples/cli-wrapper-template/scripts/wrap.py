#!/usr/bin/env python3
"""=pingcheck <host> [count]: is a host reachable, how fast, how much is lost. Wraps the system ping command.

An example of the Bolt Apps kit for wrapping any command-line tool. This file is the generic wrapper; what changes per
tool lives in config.json: the command for each OS, the exit codes, the regular expressions that read the output and the
rules for the verdict. The command is run as an argument list with no shell, so no word can add a second command."""
import json
import os
import re
import sys

import os as _os
import sys as _sys

_sys.dont_write_bytecode = True   # Bolt installs the script folder as it is: no __pycache__ in it
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))   # python -I drops the script folder from the path; the kit sits beside the script
import bolt_app_kit as kit

HERE = os.path.dirname(os.path.abspath(__file__))
FILE_WORDS = ("config.json", "fixtures.json", "bolt_app_kit.py")   # the helper files the bridge command lists, so Bolt shows them in the approval and asks again if one changes
VIEWS = ("overview", "replies", "raw", "command")
APP = "cli-wrapper-template"
OS = kit.os_name()


def load_json(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as f:
        return json.load(f)


def split_args(argv):
    a = list(argv[1:])
    n = len(FILE_WORDS)
    if len(a) >= n and [os.path.basename(x) for x in a[-n:]] == list(FILE_WORDS):
        a = a[:-n]
    return [w for w in a if w != "-"]


# ------------------------------------------------------------------ arguments: validated, never trusted

def check_host(word, cfg):
    """A host name or an IP address, and nothing else. A leading dash would be read by ping as an option, so the
    pattern needs a letter, digit or colon first. Returns None when the word is fine, else the reason."""
    if not word or len(word) > cfg["host"]["max_len"]:
        return "A host name is 1 to %d characters" % cfg["host"]["max_len"]
    if not re.match(cfg["host"]["pattern"], word):
        return "Only letters, digits, dots, dashes and colons are allowed in a host name, and it cannot start with a dash"
    return None


def check_count(word, cfg):
    c = cfg["params"]["count"]
    if word is None:
        return c["default"], None
    if not re.match(r"^[0-9]{1,3}\Z", word) or not c["min"] <= int(word) <= c["max"]:
        return None, "The count is a whole number from %d to %d" % (c["min"], c["max"])
    return int(word), None


def build_command(cfg, host, count):
    table = cfg["commands"][OS]
    wait = str(cfg["params"]["wait_s"]["default"])
    sub = {"{host}": host, "{count}": str(count), "{wait}": wait}
    return [sub.get(t, t) for t in table]


# ------------------------------------------------------------------ run and parse

def parse_output(out, rx):
    """Reads what ping printed. Every number comes from the output; a number that is not there is None, never 0."""
    replies = [(int(m.group(1)), float(m.group(2))) for m in re.finditer(rx["reply"], out)]
    def first(key, grp=1, cast=float):
        m = re.search(rx[key], out)
        return cast(m.group(grp)) if m else None
    rtt = re.search(rx["rtt"], out)
    res = {
        "replies": replies,
        "sent": first("sent", cast=int),
        "received": first("received", cast=int),
        "loss": first("loss"),
        "min": float(rtt.group(1)) if rtt else None,
        "avg": float(rtt.group(2)) if rtt else None,
        "max": float(rtt.group(3)) if rtt else None,
    }
    if res["loss"] is None and res["sent"] and res["received"] is not None:
        res["loss"] = (res["sent"] - res["received"]) * 100.0 / res["sent"]
    return res


def run_ping(cfg, cmd, deadline):
    r = kit.run(cmd, deadline=deadline, timeout=cfg["limits"]["command_timeout"], ok_rcs=tuple(int(k) for k in cfg["exit_codes"][OS]),
                max_bytes=cfg["limits"]["max_output"])
    if r.missing:
        return {"kind": "missing", "hint": cfg["tool"]["install_hint"].get(OS, "")}
    if r.timed_out:
        return {"kind": "timeout", "seconds": cfg["limits"]["command_timeout"]}
    if not r.ok:
        return {"kind": "failed", "reason": r.reason, "rc": r.rc, "out": r.out}
    meaning = cfg["exit_codes"][OS].get(str(r.rc), "")
    stats = parse_output(r.out, cfg["parse"][OS])
    if stats["loss"] is None:
        # no summary at all: the tool said something this app does not know. Show it, do not guess.
        return {"kind": "failed" if meaning != "unknown host" and "unknown host" not in meaning else "unknown_host", "reason": meaning or "unreadable output", "rc": r.rc, "out": r.out}
    return {"kind": "ok", "stats": stats, "rc": r.rc, "meaning": meaning, "out": r.out}


def cacheable(res):
    """Only a real answer is kept. A timeout, a missing tool, a failure and an unresolved name are not: the next run asks again."""
    return res.get("kind") == "ok"


def sample_result(cfg, fx):
    """Sample mode: parse a recorded output instead of running the tool, so a copy of this app has a working path before the tool is installed."""
    text = fx.get(OS)
    if not isinstance(text, str):
        return {"kind": "failed", "reason": "no sample for this system", "rc": None, "out": ""}
    stats = parse_output(text, cfg["parse"][OS])
    return {"kind": "ok", "stats": stats, "rc": 0, "meaning": "ok", "out": text} if stats["loss"] is not None else {"kind": "failed", "reason": "sample not readable", "rc": 0, "out": text}


def shape(v):
    return isinstance(v, dict) and v.get("kind") in ("ok", "unknown_host", "failed", "timeout", "missing")


# ------------------------------------------------------------------ rows

def verdict(cfg, st):
    v = cfg["verdict"]
    if st["received"] == 0 or st["loss"] >= 100:
        return "DOWN", "No reply from %s", "AlertCircle"
    if st["loss"] >= v["degraded_loss_pct"]:
        return "LOSSY", "Reachable with %s lost", "AlertCircle"
    if st["avg"] is not None and st["avg"] >= v["slow_avg_ms"]:
        return "SLOW", "Reachable but slow", "Clock"
    return "UP", "Reachable", "CheckCircle2"


def back():
    return kit.back_row("Back to the overview")


def problem_rows(res, host, cmd):
    k = res["kind"]
    again = kit.refresh_row("overview", title="Try again", subtitle="Enter to run ping again")
    if k == "missing":
        return [kit.row("ping is not installed", res["hint"] or "The command was not found on this computer", icon="AlertCircle", badge="MISSING", copy=False), again]
    if k == "timeout":
        return [kit.row("ping timed out", "No answer after %d seconds. The network may be down" % res["seconds"], icon="Clock", badge="TIMEOUT", copy=False), again]
    if k == "unknown_host":
        return [kit.row("Cannot find %s" % host, "The name does not resolve. Check the spelling, or your network and DNS", icon="AlertCircle", badge="UNKNOWN", copy=False), again]
    first = kit.clean_text((res.get("out") or "").strip().splitlines()[0], 100) if (res.get("out") or "").strip() else ""
    return [kit.row("ping failed (%s)" % res.get("reason", "error"), first or "The command gave no output", icon="AlertCircle", badge="FAILED", copy=False), again]


def build(view, cfg, res, host, count, cmd, fromcache, age):
    shown = " ".join(cmd)
    if res["kind"] != "ok":
        rows = problem_rows(res, host, cmd)
        return ([back()] if view != "overview" else []) + rows
    st = res["stats"]
    badge, head, icon = verdict(cfg, st)
    if view == "overview":
        sub = "loss %s%%" % kit.fmt_num(st["loss"], 0)
        if st["avg"] is not None:
            sub = "average %s ms, " % kit.fmt_num(st["avg"], 1) + sub
        title = (head % host) if "%s" in head else "%s: %s" % (host, head)
        rows = [kit.row(title, sub, icon=icon, badge=badge, copy=True,
                        actions=[kit.action_copy("cmd", "Copy command", shown, safe=False)])]
        if st["avg"] is not None:
            rows.append(kit.row("Average %s ms" % kit.fmt_num(st["avg"], 1), "min %s, max %s" % (kit.fmt_num(st["min"], 1), kit.fmt_num(st["max"], 1)),
                                icon="Timer", tile=kit.tile("Average", st["avg"], "ms", None, note="min %s, max %s" % (kit.fmt_num(st["min"], 1), kit.fmt_num(st["max"], 1))),
                                trend=[ms for _, ms in st["replies"]] or None))
        rows.append(kit.row("Loss %s%%" % kit.fmt_num(st["loss"], 0), "%s of %s replies" % (st["received"], st["sent"]), icon="Percent",
                            tile=kit.tile("Loss", st["loss"], "%", 100, note="%s of %s" % (st["received"], st["sent"])), badge="" if st["loss"] == 0 else "LOSS"))
        rows.append(kit.row("Replies", kit.fmt_count(len(st["replies"]), "reply", "replies"), icon="LineChart", nav={"view": "replies"}, pane="replies", copy=False))
        rows.append(kit.row("Raw output", "exactly what ping printed", icon="Terminal", nav={"view": "raw"}, pane="raw", copy=False))
        rows.append(kit.row("The command", "what ran on this %s" % OS, icon="SquareTerminal", nav={"view": "command"}, pane="command", copy=False))
        rows.append(kit.refresh_row("overview", title="Ping again", subtitle="Enter to run ping again (a result is reused for %d s)" % cfg["limits"]["result_ttl"]))
        if fromcache:
            rows.insert(1, kit.row("From a recent run", "%s ago" % kit.fmt_duration(age), icon="Clock", badge="CACHED", copy=False))
        return rows
    if view == "replies":
        if not st["replies"]:
            return [back(), kit.row("No replies", "Nothing came back to plot", icon="AlertCircle", copy=False)]
        return [kit.row("reply %s" % n, "%s ms" % kit.fmt_num(ms, 1), icon="LineChart", label=str(n), value=ms, copy=False) for n, ms in st["replies"]]
    if view == "raw":
        return [back(), kit.row("ping output", "%d lines" % len(res["out"].splitlines()), icon="Terminal", body="\n".join("    " + l for l in kit.clean_lines(res["out"], 40, cfg["limits"]["max_output"]).splitlines()), copy=False)]
    return [back(), kit.row("Command", shown, icon="SquareTerminal", body="    " + shown, copy=shown,
                            actions=[kit.action_copy("cmd", "Copy command", shown, safe=False)])]


def emit_yaml(cfg):
    app = cfg["app"]
    words = " ".join("{{scripts_dir}}/%s" % f for f in FILE_WORDS)
    cmd = "%s {{scripts_dir}}/wrap.py {{view}} {{p1}} {{p2}} " + words
    L = ["# Generated by: python3 scripts/wrap.py --emit-yaml (edit config.json, not this file)",
         "schema_version: 1", "runtime: bridge", "id: %s" % app["id"], "chip: %s" % app["chip"], "title: %s" % json.dumps(app["title"]),
         "icon: %s" % app["icon"], "description: %s" % json.dumps(app["description"]),
         'placeholder_examples: ["one.one.one.one", "example.com 5"]', "emits: Generic", "args:",
         '  - { name: view, from: "query.word(0)", default: overview }',
         '  - { name: p1, from: "query.word(1)", default: "-" }',
         '  - { name: p2, from: "query.word(2)", default: "-" }', "bridge:", "  command:"]
    for osn in ("macos", "linux"):
        L.append('    %s: "%s"' % (osn, cmd % "python3"))
    L += ["  parse: json", "  timeout_seconds: %d" % app["timeout"], "presentation:", "  widget: list", "  title_field: title",
          "  subtitle_field: subtitle", "  view_arg: view", "  right_widget:", "    kind: cards", "    mode: list_data", "    bind:",
          '      layout: "tiles"', '      title: "{{row.kpi_label}}"', '      value: "{{row.kpi_value}}"', '      unit: "{{row.kpi_unit}}"',
          '      max: "{{row.kpi_max}}"', '      trend: "{{row.trend}}"', '      subtitle: "{{row.kpi_note}}"', '      badge: "{{row.kpi_badge}}"', "  views:", "    overview: {}",
          "    replies:", "      right_widget:", "        kind: chart", "        mode: list_data", "        bind:", '          type: "%s"' % cfg["chart"]["type"],
          '          x: "label"', '          y: "value"', '          label: %s' % json.dumps(cfg["chart"]["title"]),
          "    raw:", "      right_widget:", "        kind: markdown", "        mode: selected_row", "        bind:", '          title: "{{row.title}}"', '          body: "{{row.body}}"',
          "    command:", "      right_widget:", "        kind: markdown", "        mode: selected_row", "        bind:", '          title: "{{row.title}}"', '          body: "{{row.body}}"',
          "actions:", '  - { id: copy, kind: composer, target: row, label: Copy, insert: "{{row.copy_text}}" }']
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ main

def main(argv):
    global APP
    cfg = load_json("config.json")
    APP = cfg["app"]["id"]   # a copy with a new id gets its own caches
    if "--emit-yaml" in argv:
        sys.stdout.write(emit_yaml(cfg))
        return
    if OS not in cfg["commands"]:
        kit.emit([kit.unsupported_row(OS, sorted(cfg["commands"]))])
    words = split_args(argv)
    view = "overview"
    refresh = False
    if words and words[0] in VIEWS:
        view, words = words[0], words[1:]
    if words and words[-1] == "refresh":
        refresh, words = True, words[:-1]
    lastc = kit.Cache(APP, 3600, shape=lambda v: isinstance(v, dict) and isinstance(v.get("host"), str))
    host = words[0] if words else ""
    count_word = words[1] if len(words) > 1 else None
    if not host:
        last = lastc.get("last")
        if not last:
            kit.emit([kit.row("Type a host name", "for example: =pingcheck one.one.one.one   or   =pingcheck example.com 5", icon="Terminal", copy=False)])
        host, count_word = last["host"], last.get("count")
    bad = check_host(host, cfg)
    count, bad_count = check_count(count_word, cfg)
    if bad or bad_count:
        kit.emit([kit.error_row(bad or bad_count, title="Not run: that input is not allowed")])
    cmd = build_command(cfg, host, count)
    key = "%s|%d" % (host, count)
    sample = os.environ.get("BOLT_APP_FIXTURE") == "1"
    results = kit.Cache(APP + "-results", cfg["limits"]["result_ttl"], shape=shape)
    res = None if refresh or sample else results.get(key)
    fromcache, age = res is not None, results.age(key) if res is not None else None
    if res is None and sample:
        res = sample_result(cfg, load_json("fixtures.json"))
    elif res is None:
        res = run_ping(cfg, cmd, kit.Deadline(float(cfg["limits"]["command_timeout"]) + 2))
        results.put(key, res, ok=cacheable(res))   # a timeout, a missing tool or an unresolved name is never remembered
        fromcache = False
    lastc.put("last", {"host": host, "count": None if count_word is None else count})
    rows = build(view, cfg, res, host, count, cmd, fromcache, age or 0)
    if sample and view == "overview":
        rows.insert(0, kit.row("Sample data", "A recorded ping output was parsed; nothing was run. Unset BOLT_APP_FIXTURE for the real command", icon="FileText", badge="SAMPLE", copy=False))
    kit.emit(rows)


def run(argv):
    try:
        main(argv)
    except SystemExit:
        raise
    except kit.KitError as e:   # a row the contract refuses is the author's bug: say what it is
        kit.emit([kit.error_row("Row contract: %s" % kit.clean_text(str(e), 200), title="This app could not run")])
    except Exception as e:   # one plain row: never a traceback, and the message is not shown (it could carry a key)
        if os.environ.get("BOLT_APP_DEBUG"):   # bolt-apps run sets this: the real error goes to the terminal
            import traceback
            traceback.print_exc()
        kit.emit([kit.error_row("%s while building the rows. Run the script in a terminal to see why." % e.__class__.__name__)])


if __name__ == "__main__":
    run(sys.argv)
