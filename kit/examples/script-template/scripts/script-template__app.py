#!/usr/bin/env python3
"""=script-template [view] [word]: a blank script app on the Bolt Apps kit. Copy this folder, then edit the lines marked EDIT HERE.

What it shows, in code you can read top to bottom:
  - the views: overview (tiles), items (a list with a filter word), item (one record, with Back)
  - a call to an API with a host allowlist, a refused redirect, a size cap and the key stripped from the answer
  - a cache in two layers: fresh (config cache.ttl) and an old copy (cache.stale_max) shown when the API fails
  - the offline row, the setup row for a missing key, and sample mode (BOLT_APP_FIXTURE=1, used by check)
  - --emit-yaml, which writes the app file from config.json so the two never disagree
Everything the person can see goes through kit rows, so text is cleaned and the contract is checked."""
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

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FILE_WORDS = tuple(_PFX + w for w in ("config.json", "fixtures.json", "bolt_app_kit.py",))   # the helper files the bridge command names, so Bolt shows them in the approval
VIEWS = ("overview", "items", "item")
APP = "script-template"   # replaced by config app.id at run time, so a copy with a new id has its own cache and key name
TOKEN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}\Z")   # what a nav arg may be: one plain word, never a path or text with spaces


def load_json(name):
    with open(os.path.join(HERE, _PFX + name), "r", encoding="utf-8") as f:
        return json.load(f)


def split_args(argv):
    """The last words are the helper files the command lists, not input: drop exactly that group."""
    a = list(argv[1:])
    n = len(FILE_WORDS)
    if len(a) >= n and [os.path.basename(x) for x in a[-n:]] == list(FILE_WORDS):
        a = a[:-n]
    return [w for w in a if w != "-"]


# ------------------------------------------------------------------ the network

class Fail(Exception):
    def __init__(self, kind, msg):
        Exception.__init__(self, msg)
        self.kind, self.msg = kind, msg


class _SameHost(urllib.request.HTTPRedirectHandler):
    hosts = ()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlparse(newurl)
        if u.scheme != "https" or u.hostname not in self.hosts:   # a key must never follow a redirect to another host
            raise Fail("fail", "redirected to a host this app does not use")
        return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)


def http_get(cfg, path, key):
    api = cfg["api"]
    url = api["base_url"].rstrip("/") + path
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.hostname not in cfg["hosts"]:
        raise Fail("fail", "host not allowed")
    headers = {"User-Agent": api["user_agent"], "Accept": "application/json"}
    if key:   # EDIT HERE if your API wants a header: headers["Authorization"] = "Bearer " + key
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({api.get("auth_param", "api_key"): key})
    _SameHost.hosts = tuple(cfg["hosts"])
    try:
        with urllib.request.build_opener(_SameHost).open(urllib.request.Request(url, headers=headers), timeout=api["call_timeout_s"]) as r:
            raw = r.read(api["max_bytes"] + 1)
    except urllib.error.HTTPError as e:
        raise Fail("auth" if e.code in (401, 403) else ("rate" if e.code == 429 else "fail"), "answered %d" % e.code)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Fail("fail", "timed out" if "timed out" in str(e) else "could not connect")
    if len(raw) > api["max_bytes"]:
        raise Fail("fail", "answer too large")
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        raise Fail("fail", "answer was not JSON")


def n_items(raw, cfg):
    """EDIT HERE: turn the API's answer into the records this app uses. A value that is missing or not the right type is not turned into 0:
    raise ValueError and the whole answer counts as unread."""
    f = cfg["fields"]
    out = []
    for r in raw[cfg["endpoints"]["items"]["data"]]:
        if not isinstance(r, dict):
            continue
        rid, name, count = str(r.get(f["id"], "")), r.get(f["name"]), r.get(f["count"])
        if not TOKEN.match(rid) or not isinstance(name, str) or isinstance(count, bool) or not isinstance(count, (int, float)):
            continue   # one odd record costs that record, not the list
        out.append({"id": rid, "name": name, "status": str(r.get(f["status"]) or "unknown"), "count": count})
    if not out and raw[cfg["endpoints"]["items"]["data"]]:
        raise ValueError("no record had the expected fields")
    return out


# ------------------------------------------------------------------ fetch with fresh and old caches

class Source(object):
    def __init__(self, cfg, fixture, demos):
        self.cfg, self.fixture, self.demos = cfg, fixture, demos
        root = kit.cache.default_root(APP)
        shape = lambda v: isinstance(v, dict) and isinstance(v.get("items"), list)
        self.fresh = kit.Cache(APP, cfg["cache"]["ttl"], shape, root=root + "/fresh")
        self.old = kit.Cache(APP, cfg["cache"]["stale_max"], shape, root=root + "/old")
        key_env = cfg["api"].get("key_env")
        self.secret = kit.get_secret(APP, key_env) if key_env else kit.Secret()   # keychain or ~/.config/<id>/.env; a shell variable only in a terminal
        self.key = self.secret.value or ""

    def get(self, refresh=False):
        """(items, state) where state is {"stale": age or None, "err": text}. Items is None when nothing can be shown."""
        c = self.cfg
        if not refresh and not self.fixture:
            hit = self.fresh.get("items")
            if hit is not None:
                return hit["items"], {"stale": None, "err": "", "cached": self.fresh.age("items") or 0}
        try:
            if "demo-offline" in self.demos or "demo-stale" in self.demos:
                if "demo-stale" in self.demos:
                    self.old.put("items", {"items": n_items(kit.redact_tree(load_json("fixtures.json")["items"], [self.key], c["api"].get("auth_param")), c)})
                raise Fail("fail", "could not connect")
            raw = load_json("fixtures.json")["items"] if self.fixture else http_get(c, c["endpoints"]["items"]["path"], self.key)
            raw = kit.redact_tree(raw, [self.key] if self.key else [], c["api"].get("auth_param"))   # APIs echo the key in links and messages: strip it before anything is cached or shown
            items = n_items(raw, c)
            self_link = str((raw.get("links") or {}).get("self", ""))[:300] if isinstance(raw, dict) else ""   # kept so the cache holds the API's own link, which may echo the key
        except Fail as e:
            return self._fallback(e.msg)
        except Exception:   # an odd answer (a null, a huge number, a wrong shape) is unread, never a traceback
            return self._fallback("unexpected answer")
        self.fresh.put("items", {"items": items, "self": self_link})
        self.old.put("items", {"items": items, "self": self_link})
        return items, {"stale": None, "err": "", "cached": 0}

    def _fallback(self, why):
        old = self.old.get("items")
        if old is not None:
            return old["items"], {"stale": self.old.age("items") or 0, "err": why, "cached": 0}
        return None, {"stale": None, "err": why, "cached": 0}


# ------------------------------------------------------------------ rows

def back():
    return kit.back_row("Back to the overview")


def banner(state, cfg):
    if state["stale"] is not None:
        return [kit.row("Showing an old copy", "%s is not answering (%s); this copy is %s old" % (cfg["app"]["service"], state["err"], kit.fmt_duration(state["stale"])), icon="Clock", badge="OLD COPY", copy=False)]
    if state["cached"] >= 2:
        return [kit.row("From a recent run", "%s old. Enter on Check again for fresh data" % kit.fmt_duration(state["cached"]), icon="Clock", badge="CACHED", copy=False)]
    return []


def offline_rows(cfg, state, view):
    title = "Could not reach %s" % cfg["app"]["service"]
    sub = "%s. If this is your copy, set api.base_url and hosts in config.json" % state["err"] if state["err"] else "Enter to try again"
    return ([back()] if view != "overview" else []) + [kit.row(title, sub, icon="AlertCircle", badge="OFFLINE", copy=False), kit.refresh_row(view if view in VIEWS else "overview", title="Try again", subtitle="Enter to run again")]


def setup_rows(cfg):
    name = cfg["api"]["key_env"]
    return [kit.row("Add your %s API key" % cfg["app"]["service"], kit.setup_hint(APP, name), icon="Key", badge="KEY", copy=kit.setup_hint(APP, name))]


def item_row(it, cfg):
    badge = cfg["status_badges"].get(it["status"], it["status"].upper()[:12])
    return kit.safe_row(it["name"], "%s · %s" % (it["status"], kit.fmt_num(it["count"], 0)), icon="list", badge=badge, nav={"view": "item", "arg": it["id"]},
                        item_name=it["name"], status=it["status"], count=it["count"], copy=False)


def build(view, arg, items, state, cfg, fixture):
    rows = []
    if fixture and view == "overview":
        rows.append(kit.row("Sample data", "Fixture mode: no network. Unset BOLT_APP_FIXTURE for the live API", icon="FileText", badge="SAMPLE", copy=False))
    if view == "overview":
        late = sum(1 for i in items if i["status"] == "late")
        rows += banner(state, cfg)
        rows.append(kit.row("%s: %d" % (cfg["tiles"]["count_label"], len(items)), "%d late" % late, icon="Activity", badge="LATE" if late else "OK",
                            tile=kit.tile(cfg["tiles"]["count_label"], len(items), "", None, note="%d late" % late), copy=False))
        rows.append(kit.row("All items", "the list, with a filter word", icon="list", nav={"view": "items"}, copy=False))
        rows.append(kit.refresh_row("overview", title="Check again", subtitle="Enter to fetch fresh data past the cache"))
        return rows
    if view == "items":
        word = (arg or "").lower()
        shown = [i for i in items if word in i["name"].lower()] if word and word != "refresh" else items
        out = [back()] + banner(state, cfg)
        out += [item_row(i, cfg) for i in shown[:50]]
        if not shown:
            out.append(kit.row("No match", "no item name contains %s" % kit.clean_text(word, 30), icon="Search", copy=False))
        return out
    it = next((i for i in items if i["id"] == arg), None)
    if it is None:
        return [back(), kit.row("Not found", "no item with id %s" % kit.clean_text(arg, 30), icon="AlertCircle", copy=False)]
    return [back(), kit.safe_row(it["name"], "%s · %s" % (it["status"], kit.fmt_num(it["count"], 0)), icon="file", item_name=it["name"], status=it["status"], count=it["count"],
                                 copy_raw=it["name"], tile=kit.safe_tile("Count", it["count"], note=it["status"]))]


def emit_yaml(cfg):
    app = cfg["app"]
    words = " ".join("{{scripts_dir}}/%s" % f for f in FILE_WORDS)
    L = ["# Generated by: python3 scripts/" + _SELF + " --emit-yaml (edit config.json, not this file)", "schema_version: 1", "runtime: bridge", "id: %s" % app["id"], "chip: %s" % app["chip"],
         "title: %s" % json.dumps(app["title"]), "icon: %s" % app["icon"], "description: %s" % json.dumps(app["description"]), 'placeholder_examples: ["Enter for the overview", "items", "items alpha"]',
         "emits: Generic", "args:", '  - { name: view, from: "query.word(0)", default: overview }', '  - { name: arg, from: "query.word(1)", default: "-" }', "bridge:", "  command:"]
    for osn in ("macos", "linux"):
        L.append(('    %s: "python3 {{scripts_dir}}/' + _SELF + ' {{view}} {{arg}} %s"') % (osn, words))
    L += ["  parse: json", "  timeout_seconds: %d" % app["timeout"], "presentation:", "  widget: list", "  title_field: title", "  subtitle_field: subtitle", "  view_arg: view", "  right_widget:",
          "    kind: cards", "    mode: list_data", "    bind:", '      layout: "tiles"', '      title: "{{row.kpi_label}}"', '      value: "{{row.kpi_value}}"', '      unit: "{{row.kpi_unit}}"',
          '      max: "{{row.kpi_max}}"', '      subtitle: "{{row.kpi_note}}"', '      badge: "{{row.kpi_badge}}"', "  views:", "    overview: {}",
          "    items:", "      right_widget:", "        kind: table", "        mode: list_data", "        bind:", "          columns:", "            - { field: item_name, label: Name }",
          "            - { field: status, label: Status }", "            - { field: count, label: Count, align: right }",
          "    item:", "      right_widget:", "        kind: detail", "        mode: selected_row", "        bind:", '          title: "{{row.item_name}}"', '          subtitle: "{{row.status}}"', "          fields:",
          '            - { label: Status, value: "{{row.status}}" }', '            - { label: Count, value: "{{row.count}}", copy: true }',
          "actions:", '  - { id: copy, kind: composer, target: row, label: Copy, insert: "{{row.copy_text}}" }']
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ main

def main(argv):
    global APP
    cfg = load_json("config.json")
    APP = cfg["app"]["id"]
    if "--emit-yaml" in argv:
        sys.stdout.write(emit_yaml(cfg))
        return
    words = split_args(argv)
    view = words[0] if words and words[0] in VIEWS else "overview"
    rest = words[1:] if words and words[0] in VIEWS else words
    demos = [w for w in rest if w in ("demo-offline", "demo-stale", "demo-nokey")]
    arg = " ".join(w for w in rest if w not in demos)[:60]
    env = os.environ.get("BOLT_APP_FIXTURE")
    fixture = (env == "1") if env in ("0", "1") else bool(cfg["api"]["fixture_default"])
    src = Source(cfg, fixture, demos)
    if cfg["api"].get("key_env") and "demo-nokey" in demos:
        kit.emit(setup_rows(cfg))
    if src.secret.problem:
        kit.emit([kit.row("Tighten the permissions on the key file", "Run chmod 600 on ~/.config/%s/.env, then press Enter" % APP, icon="Key", badge="KEY", copy=False)])
    items, state = src.get(refresh=(arg == "refresh"))
    if items is None:
        kit.emit(offline_rows(cfg, state, view))
    kit.emit(build(view, arg, items, state, cfg, fixture))


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
