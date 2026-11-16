#!/usr/bin/env python3
"""=insights <path to a CSV file>: totals, a trend, a breakdown and what to watch. Read-only and local.

An example of the Bolt Apps kit. This file is the generic reader and the rule runner. What changes per app lives in
config.json: the column names to look for, the limits, the insight rules and the chart titles. No network."""
import csv
import datetime
import io
import json
import math
import os
import stat
import sys

import os as _os
import sys as _sys

_sys.dont_write_bytecode = True   # Bolt installs the script folder as it is: no __pycache__ in it
_SELF = _os.path.basename(__file__)
_PFX = _SELF.partition("__")[0] + "__" if "__" in _SELF else ""   # Bolt keeps every app's scripts in ONE folder, so each file of this app is named <app id>__<name>
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("bolt_app_kit", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), _PFX + "bolt_app_kit.py"))   # the kit sits beside the script under this app's own name (python -I drops the script folder from the path, so it is loaded by path)
kit = _sys.modules.get("bolt_app_kit")   # already imported: the test suite does this; a normal run never has
if kit is None and _os.path.exists(_spec.origin):
    kit = _ilu.module_from_spec(_spec)
    _sys.modules["bolt_app_kit"] = kit
    _spec.loader.exec_module(kit)
elif kit is None and _os.path.isdir(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "bolt_app_kit")):   # a bolt_app_kit package folder beside the script
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import bolt_app_kit as kit
elif kit is None:
    raise SystemExit("script files must be named <app id>__<name>: this one is %s and %s was not found beside it. Rename the files back, and do not run the script through a link." % (_SELF, _PFX + "bolt_app_kit.py"))

HERE = os.path.dirname(os.path.abspath(__file__))
FILE_WORDS = tuple(_PFX + w for w in ("config.json", "fixtures.json", "bolt_app_kit.py",))   # the bridge command lists them so an edit asks again
VIEWS = ("overview", "trend", "breakdown", "rows", "problems")
APP = "file-insights-template"


def load_json(name):
    with open(os.path.join(HERE, _PFX + name), "r", encoding="utf-8") as f:
        return json.load(f)


def split_args(argv):
    """The last three words are the helper files Bolt was told to approve, not input. Strip exactly that triple."""
    a = list(argv[1:])
    if len(a) >= 3 and [os.path.basename(x) for x in a[-3:]] == list(FILE_WORDS):
        a = a[:-3]
    return [w for w in a if w != "-"]


# ------------------------------------------------------------------ reading

class Unreadable(Exception):
    pass


def read_text(path, max_bytes):
    """Return (text, truncated). Only a regular file is opened for real: a pipe or device would block."""
    p = os.path.expanduser(path)
    try:
        fd = os.open(p, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    except FileNotFoundError:
        raise Unreadable("No file at that path", "Check the spelling. A path with spaces needs at most 4 words here")
    except PermissionError:
        raise Unreadable("Not allowed to read that file", "The file is private to another user")
    except OSError as e:
        raise Unreadable("Could not open that file", e.__class__.__name__)
    try:
        st = os.fstat(fd)
        if stat.S_ISDIR(st.st_mode):
            raise Unreadable("That is a folder", "Type the path of a CSV file inside it")
        if not stat.S_ISREG(st.st_mode):
            raise Unreadable("That is not a regular file", "Pipes and devices are not read")
        raw = os.read(fd, max_bytes + 1) if st.st_size else b""
        while len(raw) <= max_bytes and st.st_size > len(raw):
            more = os.read(fd, max_bytes + 1 - len(raw))
            if not more:
                break
            raw += more
    finally:
        os.close(fd)
    truncated = len(raw) > max_bytes
    raw = raw[:max_bytes]
    if b"\x00" in raw[:8192]:
        raise Unreadable("That looks like a binary file", "Only text files such as CSV are read")
    return raw.decode("utf-8-sig", "replace"), truncated


def sniff_delimiter(head, candidates):
    best, score = candidates[0], 0
    for d in candidates:
        n = head.count(d)
        if n > score:
            best, score = d, n
    return best


def parse_csv(text, lim, delimiters):
    """Rows of cells, capped. Returns (header, rows, notes). A malformed file never raises."""
    notes = {"ragged": 0, "capped_rows": False, "capped_cols": False, "csv_error": ""}
    lines = text.split("\n", 1)
    delim = sniff_delimiter(lines[0], delimiters)
    csv.field_size_limit(1 << 20)
    rd = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    header, rows = None, []
    try:
        for rec in rd:
            if not rec or all(not c.strip() for c in rec):
                continue
            if header is None:
                header = [kit.clean_text(c, 60) for c in rec[: lim["max_cols"]]]
                notes["capped_cols"] = len(rec) > lim["max_cols"]
                continue
            if len(rows) >= lim["max_rows"]:
                notes["capped_rows"] = True
                break
            if len(rec) != len(header):
                notes["ragged"] += 1
            rows.append([kit.clean_text(c, lim["max_cell"]) for c in rec[: lim["max_cols"]]])
    except csv.Error as e:
        notes["csv_error"] = str(e)[:60]
    return header, rows, notes


def pick_column(header, wanted, mapping, key):
    low = [h.lower() for h in header]
    if mapping.get(key) and mapping[key].lower() in low:
        return low.index(mapping[key].lower())
    for name in wanted:
        if name in low:
            return low.index(name)
    return None


def to_number(s, currency):
    t = s.strip()
    if not t:
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(",", "").replace("_", "").rstrip("%")
    t = t.lstrip(currency + "+ ")
    if t.startswith("-"):
        neg, t = not neg, t[1:].lstrip(currency + " ")
    try:
        v = float(t)
    except ValueError:
        return None
    if not math.isfinite(v) or abs(v) > 1e15 or t.lower() in ("nan", "inf", "infinity"):
        return None
    return -v if neg else v


def to_date(s, formats):
    t = s.strip()[:10] if len(s.strip()) > 7 else s.strip()
    for f in formats:
        try:
            return datetime.datetime.strptime(t, f).date()
        except ValueError:
            continue
    return None


def analyse(header, rows, cfg):
    cols = {}
    for k in ("date", "value", "category"):
        cols[k] = pick_column(header, cfg["columns"][k], cfg.get("mapping", {}), k)
    recs, skipped, bad_dates = [], 0, 0
    for r in rows:
        def cell(i):
            return r[i] if i is not None and i < len(r) else ""
        v = to_number(cell(cols["value"]), cfg["currency"]) if cols["value"] is not None else None
        if v is None:
            skipped += 1
            continue
        d = to_date(cell(cols["date"]), cfg["date_formats"]) if cols["date"] is not None else None
        if cols["date"] is not None and d is None:
            bad_dates += 1
        recs.append({"value": v, "date": d, "category": cell(cols["category"]) or "(none)"})
    return {"cols": cols, "recs": recs, "skipped": skipped, "bad_dates": bad_dates, "n_rows": len(rows)}


def bucket(recs, max_points):
    dated = [r for r in recs if r["date"]]
    if not dated:
        return [], ""
    days = sorted(set(r["date"] for r in dated))
    unit = "day" if len(days) <= max_points else "month"
    sums = {}
    for r in dated:
        k = r["date"].isoformat() if unit == "day" else r["date"].strftime("%Y-%m")
        sums[k] = sums.get(k, 0.0) + r["value"]
    keys = sorted(sums)[-max_points:]
    return [(k, sums[k]) for k in keys], unit


def groups(recs, top=10):
    s = {}
    for r in recs:
        s[r["category"]] = s.get(r["category"], 0.0) + r["value"]
    return sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))[:top], len(s)


# ------------------------------------------------------------------ insight rules

def run_rules(cfg, a, series, grp, ngroups):
    """Each rule gives (tone, title, subtitle). Tone is WATCH, GOOD or "" (information). A rule whose input is
    missing says so instead of guessing."""
    vals = [r["value"] for r in a["recs"]]
    n = len(vals)
    total = sum(vals)
    out = []
    unit = cfg.get("unit", "")
    for rule in cfg["rules"]:
        k = rule["kind"]
        ctx = {"total": kit.fmt_num(total, 1) + unit, "n": kit.fmt_count(a["n_rows"]), "mean": kit.fmt_num(total / n, 1) if n else "unknown"}
        tone = ""
        if k == "sum":
            if not n:
                out.append((rule["id"], "WATCH", "No usable values", "No row had a number in the value column"))
                continue
        elif k == "change":
            if len(series) < 2 or series[-2][1] == 0:
                out.append((rule["id"], "", "Change: not enough periods", "Needs two dated periods with a non-zero first one"))
                continue
            (pl, pv), (ll, lv) = series[-2], series[-1]
            pct = (lv - pv) * 100.0 / abs(pv)
            ctx.update({"change": ("+" if pct >= 0 else "") + kit.fmt_num(pct, 1) + "%", "last_label": ll, "prev_label": pl})
            tone = "WATCH" if pct <= rule["watch_below_pct"] else "GOOD" if pct >= rule["good_above_pct"] else ""
        elif k == "top_share":
            if not grp or total <= 0:
                out.append((rule["id"], "", "Groups: not enough to compare", "Needs a category column and a positive total"))
                continue
            share = grp[0][1] * 100.0 / total
            ctx.update({"top": grp[0][0], "share": kit.fmt_num(share, 0), "groups": str(ngroups)})
            tone = "WATCH" if share >= rule["watch_above_pct"] else ""
        elif k == "outliers":
            if n < 8:
                continue
            mean = total / n
            sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / n)
            cnt = sum(1 for v in vals if sd > 0 and abs(v - mean) > rule["z"] * sd)
            ctx.update({"count": str(cnt)})
            tone = "WATCH" if cnt else ""
        elif k == "missing":
            pct = (a["skipped"] * 100.0 / a["n_rows"]) if a["n_rows"] else 0
            ctx.update({"pct": kit.fmt_num(pct, 1)})
            tone = "WATCH" if pct >= rule["watch_above_pct"] else ""
            if not a["skipped"]:
                continue
        else:
            continue
        out.append((rule["id"], tone, rule["title"].format(**ctx), rule["subtitle"].format(**ctx)))
    return out


# ------------------------------------------------------------------ rows

def sample_row():
    return kit.row("Sample data", "Invented numbers, not your file. Type =insights and the path of a CSV to see yours",
                   icon="FileText", copy=False, badge="SAMPLE")


def back():
    return kit.back_row("Back to the overview")


def build(view, cfg, source, a, notes, series, unit_name, grp, ngroups, sample, truncated):
    lim = cfg["limits"]
    insights = run_rules(cfg, a, series, grp, ngroups)
    watch = sum(1 for i in insights if i[1] == "WATCH")
    if view == "overview":
        rows = []
        if sample:
            rows.append(sample_row())
        rows.append(kit.row("%s" % ("Nothing to watch" if not watch else "%d to watch" % watch),
                            "%s read from %s" % (kit.fmt_count(len(a["recs"]), "row"), source), icon="CheckCircle2" if not watch else "AlertCircle",
                            badge="OK" if not watch else "WATCH", copy=False))
        total = sum(r["value"] for r in a["recs"])
        rows.append(kit.row("%s rows used" % kit.fmt_num(len(a["recs"]), 0), "%d skipped" % a["skipped"], icon="list",
                            tile=kit.tile("Rows", len(a["recs"]), "", None, note="%d skipped" % a["skipped"]), copy=False))
        for rid, tone, title, sub in insights:
            tl = kit.tile("Total", total, "", None, note="all rows") if rid == "total" and a["recs"] else None
            rows.append(kit.row(title, sub, icon="Calculator" if rid == "total" else "Activity" if tone != "WATCH" else "AlertCircle", badge=tone, tile=tl))
        rows.append(kit.row("Trend", "%s, %s" % (unit_name or "no dates", kit.fmt_count(len(series), "period")), icon="line-chart",
                            nav={"view": "trend"}, pane="trend", copy=False))
        rows.append(kit.row("Breakdown", "%s" % kit.fmt_count(ngroups, "group"), icon="Layers", nav={"view": "breakdown"}, pane="breakdown", copy=False))
        rows.append(kit.row("Rows", "first %d, as read" % lim["preview_rows"], icon="list", nav={"view": "rows"}, pane="rows", copy=False))
        prob = a["skipped"] + a["bad_dates"] + notes["ragged"]
        rows.append(kit.row("Problems", "%d things worth knowing" % (prob + (1 if truncated or notes["capped_rows"] or notes["capped_cols"] else 0)),
                            icon="AlertCircle", nav={"view": "problems"}, pane="problems", copy=False))
        return rows
    if view == "trend":
        c = cfg["charts"]["trend"]
        if not series:
            return [back(), kit.row("No dated rows", "No column named like a date was found, or no date could be read", icon="AlertCircle", pane="trend", copy=False)]
        return [kit.row("%s" % k, kit.fmt_num(v, 1), icon="line-chart", label=k, value=round(v, 2), copy=False) for k, v in series]
    if view == "breakdown":
        if not grp:
            return [kit.row("No groups", "No usable rows", icon="AlertCircle", copy=False)]
        return [kit.row(k, kit.fmt_num(v, 1), icon="Layers", label=k, value=round(v, 2), copy=False) for k, v in grp]
    if view == "rows":
        out = [kit.row("%s" % (r["category"] or "row"), "%s" % kit.fmt_num(r["value"], 2), icon="list", date=r["date"].isoformat() if r["date"] else "",
                       category=r["category"], value=round(r["value"], 2), copy=False) for r in a["recs"][: lim["preview_rows"]]]
        return out or [kit.row("No usable rows", "", icon="AlertCircle", copy=False)]
    probs = []
    if a["skipped"]:
        probs.append(("Skipped rows", "%d of %d rows had no number in the value column. They are left out, never counted as zero." % (a["skipped"], a["n_rows"])))
    if a["bad_dates"]:
        probs.append(("Unreadable dates", "%d rows have a date that none of the formats in config.json read. They count in the totals but not in the trend." % a["bad_dates"]))
    if notes["ragged"]:
        probs.append(("Uneven rows", "%d rows have a different number of cells from the header." % notes["ragged"]))
    if notes["capped_rows"]:
        probs.append(("Row cap", "Only the first %d rows are read (limits.max_rows)." % lim["max_rows"]))
    if notes["capped_cols"]:
        probs.append(("Column cap", "Only the first %d columns are read (limits.max_cols)." % lim["max_cols"]))
    if truncated:
        probs.append(("File cap", "Only the first %s of the file is read (limits.max_bytes)." % kit.fmt_bytes(lim["max_bytes"])))
    if notes["csv_error"]:
        probs.append(("CSV error", "The reader stopped early: %s" % notes["csv_error"]))
    for k, col in (("date", "date"), ("value", "value"), ("category", "category")):
        if a["cols"][k] is None:
            probs.append(("No %s column" % col, "No header matches columns.%s in config.json. Add yours to the list or to mapping." % k))
    if not probs:
        return [back(), kit.row("No problems", "Every row was read", icon="CheckCircle2", badge="OK", copy=False)]
    return [back()] + [kit.row(t, b[:80], icon="AlertCircle", body=b, copy=False) for t, b in probs]


# ------------------------------------------------------------------ yaml

def emit_yaml(cfg):
    app = cfg["app"]
    words = " ".join("{{scripts_dir}}/%s" % f for f in FILE_WORDS)
    cmd = "%s {{scripts_dir}}/" + _SELF + " {{view}} {{p1}} {{p2}} {{p3}} " + words
    ch = cfg["charts"]
    cols = []
    for c in cfg["table_columns"]:
        cols.append("            - " + json.dumps(dict((k, v) for k, v in c.items()), separators=(", ", ": ")).replace('"', ""))
    L = ["# Generated by: python3 scripts/" + _SELF + " --emit-yaml (edit config.json, not this file)",
         "schema_version: 1", "runtime: bridge", "id: %s" % app["id"], "chip: %s" % app["chip"], "title: %s" % json.dumps(app["title"]),
         "icon: %s" % app["icon"], "description: %s" % json.dumps(app["description"]),
         'placeholder_examples: ["~/Documents/sales.csv", "Enter for sample data"]', "emits: Generic", "args:",
         '  - { name: view, from: "query.word(0)", default: overview }',
         '  - { name: p1, from: "query.word(1)", default: "-" }',
         '  - { name: p2, from: "query.word(2)", default: "-" }',
         '  - { name: p3, from: "query.word(3)", default: "-" }',
         "bridge:", "  command:"]
    for osn, py in (("macos", "python3"), ("linux", "python3"), ("windows", "python")):
        L.append('    %s: "%s"' % (osn, cmd % py))
    L += ["  parse: json", "  timeout_seconds: %d" % app["timeout"], "presentation:", "  widget: list", "  title_field: title",
          "  subtitle_field: subtitle", "  view_arg: view", "  right_widget:", "    kind: cards", "    mode: list_data", "    bind:",
          '      layout: "tiles"', '      title: "{{row.kpi_label}}"', '      value: "{{row.kpi_value}}"', '      unit: "{{row.kpi_unit}}"',
          '      max: "{{row.kpi_max}}"', '      subtitle: "{{row.kpi_note}}"', '      badge: "{{row.kpi_badge}}"', "  views:", "    overview: {}"]
    for vid, key in (("trend", "trend"), ("breakdown", "breakdown")):
        L += ["    %s:" % vid, "      right_widget:", "        kind: chart", "        mode: list_data", "        bind:",
              '          type: "%s"' % ch[key]["type"], '          x: "label"', '          y: "value"', '          label: %s' % json.dumps(ch[key]["title"])]
    L += ["    rows:", "      right_widget:", "        kind: table", "        mode: list_data", "        bind:", '          totals_label: "Total"', "          columns:"] + cols
    L += ["    problems:", "      right_widget:", "        kind: markdown", "        mode: selected_row", "        bind:",
          '          title: "{{row.title}}"', '          body: "{{row.body}}"',
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
    words = split_args(argv)
    view = "overview"
    if words and words[0] in VIEWS:
        view, words = words[0], words[1:]
    lim = cfg["limits"]
    lastc = kit.Cache(APP, 3600, shape=lambda v: isinstance(v, dict) and isinstance(v.get("path"), str))
    path = " ".join(words).strip()
    sample, truncated = False, False
    source = path
    try:
        if not path:
            last = lastc.get("last")
            path = last["path"] if last and view != "overview" else ""
            source = path
        if path.startswith("demo-"):
            fx = load_json("fixtures.json")
            key = path[5:]
            if key == "huge":   # the row cap test: more rows than limits.max_rows, built in memory
                fx = {"huge": "date,amount\n" + "\n".join("2026-01-%02d,%d" % (i % 28 + 1, i) for i in range(lim["max_rows"] + 1000)) + "\n"}
            if key not in fx or key.startswith("_"):
                raise Unreadable("No such demo", "demos: " + ", ".join(sorted(k for k in fx if not k.startswith("_"))))
            text, sample, source = fx[key], True, "demo " + key
        elif not path:
            text, sample, source = load_json("fixtures.json")["sample"], True, "built-in sample"
        else:
            text, truncated = read_text(path, lim["max_bytes"])
            lastc.put("last", {"path": path})
    except Unreadable as e:
        kit.emit([kit.error_row(e.args[1], title=e.args[0])])
    except (OSError, ValueError) as e:
        kit.emit([kit.error_row("Could not read the file: %s" % e.__class__.__name__)])
    header, rows, notes = parse_csv(text, lim, cfg["delimiters"])
    if not header or not rows:
        kit.emit([kit.error_row("The file has no data rows. A header line then one row per line is expected", title="Nothing to show")])
    a = analyse(header, rows, cfg)
    series, unit_name = bucket(a["recs"], lim["max_points"])
    grp, ngroups = groups(a["recs"])
    out = build(view, cfg, source, a, notes, series, unit_name, grp, ngroups, sample, truncated)
    if sample and view == "problems":
        out.insert(1 if out and (out[0].get("nav") or {}).get("back") else 0, sample_row())
    kit.emit(out)


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
