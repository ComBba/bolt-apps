#!/usr/bin/env python3
"""=script-template [view] [words]: a working script app on the Bolt Apps kit. It searches the Art Institute of Chicago's public-domain artworks (no key) and shows
pictures. Copy this folder, then edit the lines marked EDIT HERE to point it at your own API.

What it shows, in code you can read top to bottom:
  - the views: overview (tiles and a featured artwork), items (a list with a search word), item (one artwork, with Back), pictures (a card grid) and grid (a thumbnail grid)
  - a call to an API with a host allowlist (every host it contacts is named in config.json), a refused redirect to another host, a size cap, a timeout and no cookies
  - pictures: the script fetches a small thumbnail from the allowlisted image host and puts it in the row as an inline data: image, because a Bolt user app pane
    never loads a web address. Row text fields are cut at 4,000 characters, so the image is split over fields img1 to img4 and the app file joins them
  - a cache in two layers: fresh (config cache.ttl) and an old copy (cache.stale_max) shown when the API fails; thumbnails are cached for 30 days
  - the offline row and sample mode (BOLT_APP_FIXTURE=1, used by check)
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

import base64
import concurrent.futures as cf
import html
import http.client
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
VIEWS = ("overview", "items", "item", "pictures", "grid")
APP = "script-template"   # replaced by config app.id at run time, so a copy with a new id has its own cache
TOKEN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}\Z")   # what a nav arg may be: one plain word, never a path or text with spaces
ITEM_ID = re.compile(r"^[0-9]{1,9}\Z")   # EDIT HERE: what one of your record ids looks like
IMAGE_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")   # an IIIF image id: it is put in a URL path, so it must be exactly this shape
B64 = re.compile(r"^/9j/[A-Za-z0-9+/]*={0,2}\Z")   # base64 of a JPEG (every JPEG starts with FF D8 FF, which is /9j/)
DATA_PREFIX = "data:image/jpeg;base64,"


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


# ------------------------------------------------------------------ the network: https, fixed hosts, same-host redirects, no cookies, timeout, size cap

class Fail(Exception):
    def __init__(self, kind, msg):
        Exception.__init__(self, msg)
        self.kind, self.msg = kind, msg


class _SameHost(urllib.request.HTTPRedirectHandler):
    hosts = ()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlparse(newurl)
        if u.scheme != "https" or u.port not in (None, 443) or u.hostname != urllib.parse.urlparse(req.full_url).hostname or u.hostname not in self.hosts:
            raise Fail("fail", "redirected to a host this app does not use")
        return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)


def http_bytes(cfg, url, accept, cap, timeout):
    """One GET: https to a host in cfg["hosts"] only, no cookies and no credentials, at most `cap` bytes. Returns (bytes, too_big)."""
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.port not in (None, 443) or u.hostname not in cfg["hosts"]:
        raise Fail("fail", "host not allowed")
    headers = {"User-Agent": cfg["api"]["user_agent"], "Accept": accept}   # EDIT HERE if your API wants a header: headers["Authorization"] = "Bearer " + key
    _SameHost.hosts = tuple(cfg["hosts"])
    try:
        with urllib.request.build_opener(_SameHost).open(urllib.request.Request(url, headers=headers), timeout=max(1.0, timeout)) as r:
            raw = r.read(cap + 1)
    except urllib.error.HTTPError as e:
        raise Fail("notfound" if e.code == 404 else ("rate" if e.code == 429 else "fail"), "answered %d" % e.code)
    except http.client.HTTPException:   # IncompleteRead, BadStatusLine and the like
        raise Fail("fail", "the answer was cut short")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Fail("fail", "timed out" if "timed out" in str(e) else "could not connect")
    return raw[:cap], len(raw) > cap


def http_json(cfg, url, budget):
    api = cfg["api"]
    raw, big = http_bytes(cfg, url, "application/json", api["max_bytes"], min(api["call_timeout_s"], budget))
    if big:
        raise Fail("fail", "answer too large")
    try:
        d = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        raise Fail("fail", "answer was not JSON")
    if not isinstance(d, dict):
        raise Fail("fail", "answer was not an object")
    return d


# ------------------------------------------------------------------ reading the API's answer

def one_line(v, limit):
    return kit.clean_text(v.split("\n")[0] if isinstance(v, str) else "", limit)


def n_item(r, cfg):
    """EDIT HERE: turn one record of the API's answer into the record this app uses, or None when it has no usable id or title. A value that is the wrong type is
    left out of that record, never turned into 0 or "None"."""
    f = cfg["fields"]
    if not isinstance(r, dict):
        return None
    rid, title = str(r.get(f["id"], "")), r.get(f["title"])
    img = r.get(f["image"])
    if not ITEM_ID.match(rid) or not isinstance(title, str) or not kit.clean_text(title):
        return None
    year = r.get(f["year"])
    out = {"id": rid, "title": kit.clean_text(title, 140), "artist": one_line(r.get(f["artist"]), 90), "date": kit.clean_text(r.get(f["date"]), 40),
           "year": year if isinstance(year, int) and not isinstance(year, bool) else None,
           "medium": kit.clean_text(r.get(f["medium"]), 120), "place": kit.clean_text(r.get(f["place"]), 60), "department": kit.clean_text(r.get(f["department"]), 80),
           "public": r.get(f["public"]) is True,
           "image_id": img if isinstance(img, str) and IMAGE_ID.match(img) else ""}
    d = r.get(f["description"])
    if isinstance(d, str) and d:
        out["description"] = kit.clean_lines(re.sub(r"<[^>]+>", "", html.unescape(re.sub(r"</p>|<br\s*/?>", "\n\n", d))), 12, 1400)
    for k in ("credit", "dimensions"):
        if isinstance(r.get(f[k]), str):
            out[k] = one_line(r.get(f[k]), 160)
    return out


def n_items(raw, cfg):
    """EDIT HERE: the list in the API's answer. This app keeps public-domain artworks that have a picture (the picture host serves those under CC0). An answer that has
    records but none usable is unread: raise ValueError and the whole answer counts as unread."""
    rows = raw.get(cfg["endpoints"]["items"]["data"])
    if not isinstance(rows, list):
        raise ValueError("no list in the answer")
    out = [i for i in (n_item(r, cfg) for r in rows) if i and i["public"] and i["image_id"]]
    if rows and not out and not any(isinstance(r, dict) and r.get(cfg["fields"]["public"]) is False for r in rows):
        raise ValueError("no record had the expected fields")
    return out


def total_of(raw):
    t = (raw.get("pagination") or {}).get("total") if isinstance(raw.get("pagination"), dict) else None
    return t if isinstance(t, int) and not isinstance(t, bool) and 0 <= t < 10 ** 9 else None


# ------------------------------------------------------------------ the data: fresh cache, network, old copy; thumbnails beside it

class Source(object):
    def __init__(self, cfg, fixture, demos, fx):
        self.cfg, self.fixture, self.demos, self.fx = cfg, fixture, demos, fx
        c = cfg["cache"]
        root = kit.cache.default_root(APP)
        listy = lambda v: isinstance(v, dict) and isinstance(v.get("items"), list)
        one = lambda v: isinstance(v, dict) and isinstance(v.get("item"), dict)
        thumb = lambda v: isinstance(v, dict) and isinstance(v.get("t"), str) and len(v["t"]) <= 16000 and bool(B64.match(v["t"]))
        flag = lambda v: isinstance(v, dict)
        self.fresh = kit.Cache(APP, c["ttl"], lambda v: listy(v) or one(v), root=root + "/fresh")
        self.old = kit.Cache(APP, c["stale_max"], lambda v: listy(v) or one(v), root=root + "/old")
        self.thumbs = kit.Cache(APP, c["thumb_ttl"], thumb, root=root + "/thumbs", max_entries=400)
        self.misses = kit.Cache(APP, c["miss_ttl"], flag, root=root + "/misses", max_entries=400)   # an image that could not be fetched is not asked for again for a while

    def _budget(self):
        return self.deadline - time.time()

    def _get(self, key, load, refresh):
        """(value, state): value is None when nothing can be shown. state {"stale": age or None, "err": text, "cached": age}."""
        if not refresh and not self.fixture:
            hit = self.fresh.get(key)
            if hit is not None:
                return hit, {"stale": None, "err": "", "cached": self.fresh.age(key) or 0}
        self.deadline = time.time() + self.cfg["api"]["deadline_s"]
        try:
            if "demo-offline" in self.demos or "demo-stale" in self.demos:
                if "demo-stale" in self.demos:
                    self.old.put(key, load(True))
                raise Fail("fail", "could not connect")
            val = load(self.fixture)
        except Fail as e:
            if e.kind == "notfound":
                return {"missing": True}, {"stale": None, "err": "", "cached": 0}
            return self._fallback(key, e.msg)
        except Exception:   # an odd answer (a null, a huge number, a wrong shape) is unread, never a traceback
            return self._fallback(key, "unexpected answer")
        self.fresh.put(key, val)
        self.old.put(key, val)
        return val, {"stale": None, "err": "", "cached": 0}

    def _fallback(self, key, why):
        old = self.old.get(key)
        if old is not None:
            return old, {"stale": self.old.age(key) or 0, "err": why, "cached": 0}
        return None, {"stale": None, "err": why, "cached": 0}

    def search(self, word, typed, refresh):
        """The artworks for a search word. In sample mode the recorded answer is filtered by the word on this side."""
        cfg = self.cfg
        ep = cfg["endpoints"]["items"]

        def load(sample):
            if sample:
                raw = self.fx["search"]
                items = n_items(raw, cfg)
                if typed:
                    items = [i for i in items if word.lower() in (i["title"] + " " + i["artist"]).lower()]
            else:
                q = [(ep["query_param"], word)] + sorted(ep.get("fixed_params", {}).items()) + [("limit", str(ep["limit"])), ("fields", ep["fields"])]
                raw = http_json(cfg, cfg["api"]["base_url"].rstrip("/") + ep["path"] + "?" + urllib.parse.urlencode(q), self._budget())   # typed text is only percent-encoded, into the query
                items = n_items(raw, cfg)
            return {"items": items, "total": total_of(raw)}
        val, state = self._get("s:" + word.lower(), load, refresh)
        return (val["items"], val.get("total")) if val else (None, None), state

    def detail(self, rid, refresh):
        cfg = self.cfg
        ep = cfg["endpoints"]["item"]

        def load(sample):
            if sample:
                raw = self.fx["details"].get(rid)
                if raw is None:   # a recorded list row with no recorded detail: show what the list knows
                    hit = next((i for i in n_items(self.fx["search"], cfg) if i["id"] == rid), None)
                    if hit is None:
                        raise Fail("notfound", "not found")
                    return {"item": hit}
            else:
                raw = http_json(cfg, cfg["api"]["base_url"].rstrip("/") + ep["path"] + rid + "?" + urllib.parse.urlencode([("fields", ep["fields"])]), self._budget())
            it = n_item(raw.get(ep["data"]), cfg)
            if it is None:
                raise Fail("notfound", "not found")
            return {"item": it}
        val, state = self._get("d:" + rid, load, refresh)
        if val is not None and val.get("missing"):
            return "missing", state
        return (val["item"] if val else None), state

    # ---- thumbnails

    def fetch_thumb(self, image_id):
        """A JPEG from the picture host as base64, or None. Tries the widths in config images.widths, widest first, until one fits images.max_bytes."""
        im = self.cfg["images"]
        for w in im["widths"]:
            try:
                raw, big = http_bytes(self.cfg, "%s/%s/full/%d,/0/default.jpg" % (im["base_url"].rstrip("/"), image_id, w), "image/jpeg", im["max_bytes"], min(im["call_timeout_s"], self._thumb_left()))
            except Fail:
                return None
            if big:
                continue   # too many bytes for the row fields: ask for a smaller one
            return base64.b64encode(raw).decode("ascii") if raw[:3] == b"\xff\xd8\xff" else None
        return None

    def _thumb_left(self):
        return max(1.0, self._thumb_end - time.time())

    def attach_thumbs(self, items, network):
        """Set item["img"] to an inline data: URL (or ""). Sample mode reads the recorded thumbnails; a live run reads the thumbnail cache and, when `network` is true, fetches the
        missing ones together with a small time budget. A failed one is left blank, never an error."""
        im = self.cfg["images"]
        need = []
        for it in items:
            b = None
            if self.fixture:
                b = self.fx.get("thumbs", {}).get(it["image_id"])
                b = b if isinstance(b, str) and B64.match(b) else None
            else:
                hit = self.thumbs.get(it["image_id"]) if it["image_id"] else None
                b = hit["t"] if hit else None
                if b is None and network and it["image_id"] and self.misses.get(it["image_id"]) is None and it["image_id"] not in need:
                    need.append(it["image_id"])
            it["img"] = DATA_PREFIX + b if b and len(DATA_PREFIX) + len(b) <= im["chunk_chars"] * im["max_chunks"] else ""
        if not need:
            return
        self._thumb_end = time.time() + im["budget_s"]
        ex = cf.ThreadPoolExecutor(max_workers=im["workers"])
        futs = dict((ex.submit(self.fetch_thumb, i), i) for i in need)
        done, _ = cf.wait(list(futs), timeout=im["budget_s"])
        ex.shutdown(wait=False)
        got = {}
        for f in done:
            try:
                got[futs[f]] = f.result()
            except Exception:
                got[futs[f]] = None
        for iid in need:
            b = got.get(iid)
            if b and B64.match(b) and len(DATA_PREFIX) + len(b) <= im["chunk_chars"] * im["max_chunks"]:
                self.thumbs.put(iid, {"t": b})
                for it in items:
                    if it["image_id"] == iid:
                        it["img"] = DATA_PREFIX + b
            elif iid in got:   # answered with nothing usable (not a timeout that left it unfinished): do not ask again for a while
                self.misses.put(iid, {"m": 1})


# ------------------------------------------------------------------ rows

def back(sub="Back to the overview"):
    return kit.back_row(sub)


def banner(state, cfg):
    if state["stale"] is not None:
        return [kit.row("Showing an old copy", "%s is not answering (%s); this copy is %s old" % (cfg["app"]["service"], state["err"], kit.fmt_duration(state["stale"])), icon="Clock", badge="OLD COPY", copy=False)]
    if state["cached"] >= 2:
        return [kit.row("From a recent run", "%s old. Enter on Check again for fresh data" % kit.fmt_duration(state["cached"]), icon="Clock", badge="CACHED", copy=False)]
    return []


def sample_row():
    return kit.row("Sample data", "Recorded answers, no network. A shipped app runs live", icon="FileText", badge="SAMPLE", copy=False)


def offline_rows(cfg, state, view):
    title = "Could not reach %s" % cfg["app"]["service"]
    sub = "%s. If this is your copy, check api.base_url and hosts in config.json" % state["err"] if state["err"] else "Enter to try again"
    return ([back("Back to the overview")] if view != "overview" else []) + [kit.row(title, sub, icon="AlertCircle", badge="OFFLINE", copy=False),
                                                                            kit.refresh_row("overview" if view == "item" else view, title="Try again", subtitle="Enter to run again")]


def img_fields(img, cfg):
    """The picture as fields img1 to img4: a row text field is cut at 4,000 characters, so the app file joins them with {{row.img1}}{{row.img2}}...."""
    im = cfg["images"]
    n, size = im["max_chunks"], im["chunk_chars"]
    if not img or len(img) > n * size:
        return {}
    return dict(("img%d" % (k + 1), img[k * size:(k + 1) * size]) for k in range(n) if img[k * size:(k + 1) * size])


def art_row(it, cfg, nav=True, full=False):
    """One artwork. The same fields feed the list, the preview pane, the grids and the detail, so a row can move between views."""
    a = cfg["attribution"]
    page = cfg["links"]["item_page"] + it["id"]
    sub = " · ".join(x for x in (it["artist"], it["date"]) if x)
    body = [a["line"]]
    if full:
        body = [it.get("description", ""), "", "%s%s" % ("Credit: %s. " % it["credit"] if it.get("credit") else "", "Size: %s" % it["dimensions"] if it.get("dimensions") else "")]
        body += ["", a["line"] + (". " + a["description_line"] if it.get("description") else "")]
    share = " - ".join(x for x in (it["title"], sub, page) if x)
    kw = dict(a_artist=it["artist"], a_date=it["date"], a_medium=it["medium"], a_origin=it["place"], a_rights="Public domain (CC0)" if it["public"] else "Not public domain",
              share_text=share, open_url=page, body="\n".join(x for x in body if x is not None).strip())
    kw.update(img_fields(it.get("img", ""), cfg))
    if nav:
        return kit.safe_row(it["title"], sub, icon="Image", nav={"view": "item", "arg": it["id"]}, copy=False, **kw)
    return kit.safe_row(it["title"], sub, icon="Image", copy_raw=share, **kw)


def build(view, arg, items, total, state, cfg, fixture, word):
    rows = []
    if fixture:
        rows.append(sample_row())
    if view == "overview":
        rows += banner(state, cfg)
        t = cfg["tiles"]
        rows.append(kit.row("%s: %d" % (t["shown_label"], len(items)), "public-domain artworks for %s" % kit.clean_text(word, 40), icon="Activity",
                            tile=kit.safe_tile(t["shown_label"], len(items), note="for %s" % kit.clean_text(word, 40)), body=cfg["attribution"]["line"], copy=False))
        if total is not None:
            rows.append(kit.row("%s: %s" % (t["matches_label"], format(total, ",")), "public-domain artworks in the whole collection match %s" % kit.clean_text(word, 40), icon="Search",
                                tile=kit.safe_tile(t["matches_label"], total, note="in the collection"), body=cfg["attribution"]["line"], copy=False))
        if items:
            rows.append(art_row(items[0], cfg))
        rows.append(kit.row("Search artworks", "a list: type a word after items, for example items water lilies", icon="Search", nav={"view": "items"}, body="Press Enter for the list. The preview pane shows a small picture, the facts and where to read more.", copy=False))
        rows.append(kit.row("Pictures", "the same artworks as a grid of cards", icon="Image", nav={"view": "pictures"}, body="Press Enter for the card grid.", copy=False))
        rows.append(kit.row("Thumbnails", "the same artworks as a plain picture grid", icon="Image", nav={"view": "grid"}, body="Press Enter for the picture grid.", copy=False))
        rows.append(kit.refresh_row("overview", title="Check again", subtitle="Enter to fetch fresh data past the cache"))
        return rows
    if view in ("items", "pictures", "grid"):
        out = [back()] + rows + banner(state, cfg)
        out += [art_row(i, cfg) for i in items]
        if not items:
            out.append(kit.row("No match", "no public-domain artwork with a picture matches %s" % kit.clean_text(word, 40), icon="Search", body="Try a painter or a subject: monet, hokusai, cat, ship.", copy=False))
        return out
    it = items
    return [back("Back to the list")] + rows + banner(state, cfg) + [art_row(it, cfg, nav=False, full=True),
            kit.row("Attribution", "%s" % cfg["attribution"]["line"], icon="BookOpen", body="\n".join([cfg["attribution"]["line"]] + ([cfg["attribution"]["description_line"]] if it.get("description") else []) + ["Source: " + cfg["links"]["item_page"] + it["id"]]), copy=False)]


# ------------------------------------------------------------------ the app file, written from config.json

_PREVIEW = [
    "kind: entity_preview", "mode: selected_row", "bind:",
    '  title: "{{row.title}}"', '  subtitle: "{{row.subtitle}}"',
    '  image_url: "{{row.img1}}{{row.img2}}{{row.img3}}{{row.img4}}"',
    "  tiles_above:", '    title: "{{row.kpi_label}}"', '    value: "{{row.kpi_value}}"', '    unit: "{{row.kpi_unit}}"', '    max: "{{row.kpi_max}}"', '    subtitle: "{{row.kpi_note}}"', '    badge: "{{row.kpi_badge}}"',
    "  fields:", '    - { label: ARTIST, value: "{{row.a_artist}}" }', '    - { label: DATE, value: "{{row.a_date}}" }', '    - { label: MEDIUM, value: "{{row.a_medium}}" }',
    '    - { label: ORIGIN, value: "{{row.a_origin}}" }', '    - { label: RIGHTS, value: "{{row.a_rights}}" }',
    '  body: "{{row.body}}"', "  actions:", '    - "open"', '    - "copy"']


def _indent(lines, n):
    return [" " * n + x for x in lines]


def emit_yaml(cfg):
    app = cfg["app"]
    words = " ".join("{{scripts_dir}}/%s" % f for f in FILE_WORDS)
    L = ["# Generated by: python3 scripts/" + _SELF + " --emit-yaml (edit config.json, not this file)", "schema_version: 1", "runtime: bridge", "id: %s" % app["id"], "chip: %s" % app["chip"],
         "title: %s" % json.dumps(app["title"]), "icon: %s" % app["icon"], "description: %s" % json.dumps(app["description"]), 'placeholder_examples: ["Enter for the overview", "items", "items water lilies", "pictures", "grid hokusai"]',
         "emits: Generic", "args:", '  - { name: view, from: "query.word(0)", default: overview }', '  - { name: arg, from: "query.word(1)", default: "-" }',
         '  - { name: arg2, from: "query.word(2)", default: "-" }', '  - { name: arg3, from: "query.word(3)", default: "-" }', "bridge:", "  command:"]
    for osn in ("macos", "linux"):
        L.append(('    %s: "python3 {{scripts_dir}}/' + _SELF + ' {{view}} {{arg}} {{arg2}} {{arg3}} %s"') % (osn, words))
    L += ["  parse: json", "  timeout_seconds: %d" % app["timeout"], "presentation:", "  widget: list", "  title_field: title", "  subtitle_field: subtitle", "  view_arg: view", "  right_widget:"]
    L += _indent(_PREVIEW, 4)
    L += ["  views:", "    overview:", "      right_widget:"] + _indent(_PREVIEW, 8) + ["    items:", "      right_widget:"] + _indent(_PREVIEW, 8)
    L += ["    item:", "      right_widget:"] + _indent(_PREVIEW, 8)
    L += ["    pictures:", "      right_widget:", "        kind: cards", "        mode: list_data", "        bind:", '          layout: "grid"', '          title: "{{row.title}}"', '          subtitle: "{{row.a_artist}}"',
          '          image: "{{row.img1}}{{row.img2}}{{row.img3}}{{row.img4}}"', '          footer: "{{row.a_date}}"',
          "    grid:", "      right_widget:", "        kind: image_grid", "        mode: list_data", "        bind:", '          src: "{{row.img1}}{{row.img2}}{{row.img3}}{{row.img4}}"', '          caption: "{{row.title}}"',
          '          alt: "{{row.title}}, {{row.a_artist}}"', "          columns: 3",
          "actions:", '  - { id: open, kind: url, target: row, label: "Open source", url_template: "{{row.open_url}}" }', '  - { id: copy, kind: composer, target: row, label: "Copy summary", insert: "{{row.share_text}}" }']
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
    first = words[0].lower() if words else ""
    view = first if first in VIEWS else ("items" if first and not first.startswith("demo-") else "overview")   # a first word that is not a view is a search word
    rest = words[1:] if first in VIEWS else words
    demos = [w for w in rest if w in ("demo-offline", "demo-stale")]
    arg = " ".join(w for w in rest if w not in demos)[:60]
    env = os.environ.get("BOLT_APP_FIXTURE")
    fixture = (env == "1") if env in ("0", "1") else bool(cfg["api"]["fixture_default"])
    fx = load_json("fixtures.json") if fixture else {}
    src = Source(cfg, fixture, demos, fx)
    refresh = arg == "refresh"
    if view == "item":
        rid = arg if ITEM_ID.match(arg) else ""
        if not rid:
            kit.emit([back(), kit.row("Not found", "no artwork with id %s" % kit.clean_text(arg, 30), icon="AlertCircle", copy=False)])
        it, state = src.detail(rid, False)
        if it == "missing":
            kit.emit([back(), kit.row("Not found", "no artwork with id %s" % rid, icon="AlertCircle", body="The collection has no artwork with this id.", copy=False)])
        if it is None:
            kit.emit(offline_rows(cfg, state, view))
        if it["public"] and it["image_id"]:
            src.attach_thumbs([it], network=state["stale"] is None)
        else:
            it["img"] = ""
        kit.emit(build(view, arg, it, None, state, cfg, fixture, ""))
    default = cfg["endpoints"]["items"]["default_query"]
    typed_words = [] if refresh else (rest if view != "overview" else [])
    word = kit.clean_text(" ".join(w for w in typed_words if w not in demos), 40) if view != "overview" else ""
    typed = len(word) >= 2
    if view != "overview" and word and not typed:
        kit.emit([back(), kit.row("Type a longer word", "at least two letters, for example: =%s items monet" % cfg["app"]["chip"], icon="Search", copy=False)])
    shown_word = word if typed else default
    (items, total), state = src.search(shown_word, typed, refresh)
    if items is None:
        kit.emit(offline_rows(cfg, state, view))
    src.attach_thumbs(items, network=state["stale"] is None)
    kit.emit(build(view, arg, items, total, state, cfg, fixture, shown_word))


def run(argv):
    try:
        main(argv)
    except SystemExit:
        raise
    except kit.KitError as e:   # a row the contract refuses is the author's bug: say what it is
        kit.emit([kit.error_row("Row contract: %s" % kit.clean_text(str(e), 200), title="This app could not run")])
    except Exception as e:   # one plain row: never a traceback, and the message is not shown
        if os.environ.get("BOLT_APP_DEBUG"):   # bolt-apps run sets this: the real error goes to the terminal
            import traceback
            traceback.print_exc()
        kit.emit([kit.error_row("%s while building the rows. Run the script in a terminal to see why." % e.__class__.__name__)])


if __name__ == "__main__":
    run(sys.argv)
