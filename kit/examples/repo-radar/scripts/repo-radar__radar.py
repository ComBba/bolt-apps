#!/usr/bin/env python3
"""=repo-radar owner/repo [vs owner/repo]: one verdict from GitHub, npm, OSV and Hacker News, fetched in parallel.

An example of the Bolt Apps kit for joining several remote APIs. The sources are separate systems; they are joined on
the repository (owner/repo) and its npm package, and the join is checked: an npm package whose repository field points
at another repo is NOT used. Weights, thresholds and TTLs live in config.json. No key is needed; a GitHub token is
optional and is read with get_secret (keychain, then ~/.config/repo-radar/.env), never from a shell variable."""
import calendar
import concurrent.futures as cf
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

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
FILE_WORDS = tuple(_PFX + w for w in ("config.json", "fixtures.json", "bolt_app_kit.py",))
VIEWS = ("overview", "releases", "vulns", "downloads", "discussion", "since", "compare")
APP = "repo-radar"
SPEC = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100})(?::((?:@[a-z0-9-~][a-z0-9-._~]*/)?[a-z0-9-~][a-z0-9-._~]{0,213}))?\Z")
DEMOS = ("demo-osv-down", "demo-github-limit", "demo-npm-none", "demo-hn-down")


def load_json(name):
    with open(os.path.join(HERE, _PFX + name), "r", encoding="utf-8") as f:
        return json.load(f)


def split_args(argv):
    a = list(argv[1:])
    if len(a) >= 3 and [os.path.basename(x) for x in a[-3:]] == list(FILE_WORDS):
        a = a[:-3]
    return [w for w in a if w != "-"]


# ------------------------------------------------------------------ http, with an allowlist of hosts

class Fail(Exception):
    def __init__(self, kind, msg, meta=None):
        Exception.__init__(self, msg)
        self.kind, self.msg, self.meta = kind, msg, meta or {}


class _Redirects(urllib.request.HTTPRedirectHandler):
    hosts = ()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlparse(newurl)
        if u.scheme != "https" or u.hostname not in self.hosts:
            raise Fail("fail", "redirected to a host this app does not use")
        return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)


def http(cfg, url, body=None, token=None):
    """GET, or POST of a JSON body. Returns (json, response headers). Raises Fail with a plain reason."""
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.hostname not in cfg["hosts"]:
        raise Fail("fail", "host not allowed")
    h = {"User-Agent": cfg["api"]["user_agent"], "Accept": "application/json"}
    if body is not None:
        h["Content-Type"] = "application/json"
    if token and u.hostname == "api.github.com":   # the token goes to GitHub only
        h["Authorization"] = "Bearer " + token
    _Redirects.hosts = tuple(cfg["hosts"])
    op = urllib.request.build_opener(_Redirects)
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers=h)
    try:
        with op.open(req, timeout=cfg["api"]["call_timeout_s"]) as r:
            raw = r.read(cfg["api"]["max_bytes"] + 1)
            hd = dict((k.lower(), v) for k, v in r.headers.items())
    except urllib.error.HTTPError as e:
        hd = dict((k.lower(), v) for k, v in e.headers.items())
        if e.code in (403, 429) and hd.get("x-ratelimit-remaining") == "0":
            raise Fail("limited", "rate limit reached", {"reset": hd.get("x-ratelimit-reset")})
        if e.code == 404:
            raise Fail("none", "not found")
        raise Fail("fail", "answered %d" % e.code)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Fail("fail", "could not connect" if not isinstance(getattr(e, "reason", None), TimeoutError) and "timed out" not in str(e) else "timed out")
    if len(raw) > cfg["api"]["max_bytes"]:
        raise Fail("fail", "answer too large")
    try:
        return json.loads(raw.decode("utf-8", "replace")), hd
    except ValueError:
        raise Fail("fail", "answer was not JSON")


# ------------------------------------------------------------------ normalise: raw API answer to what the app uses

def need_int(raw, key):
    """A whole, finite number from an answer. A missing, text, boolean, infinite or absurd value is an unexpected answer."""
    v = raw.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (isinstance(v, float) and (not math.isfinite(v) or v != int(v))) or abs(v) > 1e15:
        raise ValueError("%s is not a whole number" % key)
    return int(v)


def opt_int(raw, key, default=0):
    return default if raw.get(key) is None else need_int(raw, key)


def ts(s):
    try:
        return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def repo_slug(v):
    s = v.get("url") if isinstance(v, dict) else v
    if not isinstance(s, str):
        return None
    m = re.search(r"github(?:\.com)?[:/]([^/\s]+)/([^/#?\s]+?)(?:\.git)?(?:[/#?].*)?\Z", s) or re.match(r"^([^/\s:]+)/([^/\s]+)\Z", s)
    return ("%s/%s" % (m.group(1), m.group(2))).lower() if m else None


def n_repo(raw):
    lic = raw.get("license") or {}
    return {"stars": need_int(raw, "stargazers_count"), "forks": need_int(raw, "forks_count"), "issues": need_int(raw, "open_issues_count"),
            "pushed": ts(raw.get("pushed_at")), "archived": bool(raw.get("archived")), "license": lic.get("spdx_id") or "none",
            "url": raw.get("html_url") or "", "description": raw.get("description") or "", "name": raw.get("full_name") or ""}


def n_releases(raw):
    return [{"tag": r.get("tag_name") or "?", "at": ts(r.get("published_at")), "pre": bool(r.get("prerelease")), "url": r.get("html_url") or "",
             "body": (r.get("body") or "")[:1500]} for r in raw if isinstance(r, dict) and not r.get("draft")]


def n_npm(raw):
    return {"name": raw.get("name"), "version": raw.get("version"), "repo": repo_slug(raw.get("repository")), "license": raw.get("license") if isinstance(raw.get("license"), str) else "",
            "deprecated": raw.get("deprecated") if isinstance(raw.get("deprecated"), str) else None}


def n_week(raw):
    return {"n": need_int(raw, "downloads")}


def n_month(raw):
    rows = raw["downloads"]
    if not isinstance(rows, list):
        raise ValueError("downloads is not a list")
    return {"days": [(str(d["day"])[:10], need_int(d, "downloads")) for d in rows]}


def n_osv(raw):
    out = []
    for v in raw.get("vulns", []) or []:
        sev = str((v.get("database_specific") or {}).get("severity") or "UNKNOWN").upper()
        fixed = sorted(set(e["fixed"] for a in v.get("affected", []) for r in a.get("ranges", []) for e in r.get("events", []) if "fixed" in e))
        out.append({"id": v.get("id") or "?", "summary": v.get("summary") or "", "sev": sev, "published": ts(v.get("published")), "fixed": fixed,
                    "cve": [x for x in v.get("aliases", []) if x.startswith("CVE-")][:2]})
    return out


def n_hn(raw):
    hits = raw.get("hits")
    if not isinstance(hits, list):
        raise ValueError("no hits list: the answer is unread, not zero threads")
    return {"total": need_int(raw, "nbHits"), "stories": [{"id": str(h.get("objectID")), "title": h.get("title") or "", "points": opt_int(h, "points"),
            "comments": opt_int(h, "num_comments"), "at": ts(h.get("created_at")), "url": "https://news.ycombinator.com/item?id=%s" % urllib.parse.quote(str(h.get("objectID")), safe="")} for h in hits if isinstance(h, dict)]}


def trim(task, raw):
    """What --record keeps from a real answer, so fixtures.json stays small and holds no personal data."""
    if task == "gh_repo":
        return dict((k, raw.get(k)) for k in ("full_name", "stargazers_count", "forks_count", "open_issues_count", "pushed_at", "archived", "license", "html_url", "description"))
    if task == "gh_releases":
        return [dict((k, r.get(k)) for k in ("tag_name", "published_at", "prerelease", "draft", "html_url")) | {"body": (r.get("body") or "")[:400]} for r in raw[:8]]
    if task == "npm_latest":
        return dict((k, raw.get(k)) for k in ("name", "version", "repository", "license", "deprecated"))
    if task == "osv_all" or task == "osv_latest":
        return {"vulns": [dict((k, v.get(k)) for k in ("id", "summary", "aliases", "published", "affected", "database_specific")) | {"affected": [{"ranges": a.get("ranges", [])} for a in v.get("affected", [])][:2]} for v in raw.get("vulns", [])[:30]]}
    if task == "hn":
        return {"nbHits": raw.get("nbHits"), "hits": [dict((k, h.get(k)) for k in ("objectID", "title", "points", "num_comments", "created_at")) for h in raw.get("hits", [])[:5]]}
    return raw


# ------------------------------------------------------------------ tasks

def pin_url(cfg, url):
    """The link the Open button may follow: https on one of config link_hosts, or nothing."""
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return ""
    return url if isinstance(url, str) and u.scheme == "https" and u.hostname in cfg["link_hosts"] and not u.username else ""


def urls(spec, pkg):
    o, r = spec
    q = urllib.parse.quote(pkg, safe="@") if pkg else ""
    return {
        "gh_repo": ("github", "https://api.github.com/repos/%s/%s" % (urllib.parse.quote(o, safe=""), urllib.parse.quote(r, safe="")), None, n_repo),
        "gh_releases": ("github", "https://api.github.com/repos/%s/%s/releases?per_page=8" % (urllib.parse.quote(o, safe=""), urllib.parse.quote(r, safe="")), None, n_releases),
        "npm_latest": ("npm", "https://registry.npmjs.org/%s/latest" % q, None, n_npm),
        "npm_week": ("npm", "https://api.npmjs.org/downloads/point/last-week/%s" % q, None, n_week),
        "npm_month": ("npm", "https://api.npmjs.org/downloads/range/last-month/%s" % q, None, n_month),
        "osv_all": ("osv", "https://api.osv.dev/v1/query", {"package": {"name": pkg, "ecosystem": "npm"}}, n_osv),
        "hn": ("hn", "https://hn.algolia.com/api/v1/search?query=%s&restrictSearchableAttributes=url&tags=story&hitsPerPage=5" % urllib.parse.quote("github.com/%s/%s" % (o, r), safe=""), None, n_hn),
    }


class Ctx(object):
    def __init__(self, cfg, fixtures, fixture, token, now, force, record, demos):
        self.cfg, self.fx, self.fixture, self.token, self.now, self.force, self.record, self.demos = cfg, fixtures, fixture, token, now, force, record, demos
        root = kit.cache.default_root(APP)
        self.fresh, self.stale = {}, {}
        for s, d in cfg["sources"].items():
            self.fresh[s] = kit.Cache(APP, d["ttl"], shape=lambda v: isinstance(v, dict), root=root + "/fresh-" + s)
            self.stale[s] = kit.Cache(APP, cfg["stale_max_s"], shape=lambda v: isinstance(v, dict), root=root + "/stale-" + s)
        self.meta = {}
        self.recorded = {}
        self.t_end = time.time() + cfg["api"]["deadline_s"]   # one deadline for everything this run starts, a compare included


def fetch_task(ctx, key, spec, pkg, task, version=None):
    """One call. Returns {"ok", "data", "ms", "cached", "age", "stale", "err", "kind"}. Never raises."""
    source, url, body, norm = urls(spec, pkg)[task] if task != "osv_latest" else ("osv", "https://api.osv.dev/v1/query", {"package": {"name": pkg, "ecosystem": "npm"}, "version": version}, n_osv)
    ck = "%s|%s|%s" % (spec[0] + "/" + spec[1], task, version or pkg or "")
    res = {"ok": False, "data": None, "ms": None, "cached": False, "age": 0, "stale": False, "err": "", "kind": "fail", "source": source}
    if source == "github" and "demo-github-limit" in ctx.demos:
        res.update(kind="limited", err="rate limit reached (demo)")
        return res
    if source == "osv" and "demo-osv-down" in ctx.demos:
        return fall_back(ctx, ck, res, "could not connect (demo)")
    if source == "npm" and "demo-npm-none" in ctx.demos:
        res.update(kind="none", err="no such package (demo)")
        return res
    if not ctx.force:
        hit = ctx.fresh[source].get(ck) if not ctx.fixture else None
        if hit is not None:
            res.update(ok=True, data=hit["d"], cached=True, age=ctx.fresh[source].age(ck) or 0, kind="ok")
            return res
    t0 = time.time()
    try:
        if ctx.fixture:
            fx = ctx.fx.get("repos", {}).get(spec[0] + "/" + spec[1])
            if fx is None or task not in fx:
                raise Fail("none" if task.startswith("npm") or task.startswith("osv") else "fail", "not in the recorded sample")
            raw = fx[task]
            if task == "osv_latest" and task not in fx:
                raw = {"vulns": []}
            h0 = fx.get("_headers", {}) if source == "github" else {}
            hd = {"x-ratelimit-limit": h0.get("limit"), "x-ratelimit-remaining": h0.get("remaining")} if h0 else {}
            if "demo-hn-down" in ctx.demos and source == "hn":
                raise Fail("fail", "timed out (demo)")
        else:
            raw, hd = http(ctx.cfg, url, body, ctx.token)
        if ctx.record is not None:
            ctx.recorded[task] = trim(task, raw)
        if source == "github" and hd.get("x-ratelimit-limit"):
            ctx.meta["github"] = {"limit": hd.get("x-ratelimit-limit"), "remaining": hd.get("x-ratelimit-remaining")}
        data = norm(raw)
    except Fail as e:
        if e.kind in ("none", "limited"):
            res.update(kind=e.kind, err=e.msg, meta=e.meta)
            return res
        return fall_back(ctx, ck, res, e.msg)
    except Exception:   # also OverflowError and RecursionError from an odd answer: it is unread, never a traceback
        return fall_back(ctx, ck, res, "unexpected answer")
    res.update(ok=True, data=data, ms=int((time.time() - t0) * 1000), kind="ok")
    if not ctx.fixture:
        ctx.fresh[source].put(ck, {"d": data})
        ctx.stale[source].put(ck, {"d": data})
    return res


def fall_back(ctx, ck, res, why):
    src = res["source"]
    old = ctx.stale[src].get(ck) if not ctx.fixture or "demo-hn-down" in ctx.demos or "demo-osv-down" in ctx.demos else None
    if old is None and ctx.fixture and ("demo-hn-down" in ctx.demos or "demo-osv-down" in ctx.demos):
        old = None
    if old is not None:
        res.update(ok=True, data=old["d"], stale=True, age=ctx.stale[src].age(ck) or 0, err=why, kind="ok")
    else:
        res.update(err=why, kind="fail")
    return res


def gather(ctx, spec, pkg_override):
    """Run every call for one repo in a pool. OSV waits for npm, because it needs the package name checked first."""
    cfg = ctx.cfg
    pkg = pkg_override or spec[1].lower()
    ex = cf.ThreadPoolExecutor(max_workers=cfg["api"]["workers"])
    t0 = time.time()
    futs = {}
    for task in ("gh_repo", "gh_releases", "npm_latest", "npm_week", "npm_month", "hn"):
        futs[task] = ex.submit(fetch_task, ctx, None, spec, pkg, task)

    def osv():
        npm = futs["npm_latest"].result(timeout=max(0.1, ctx.t_end - time.time()))
        if not npm["ok"] or (npm["data"]["repo"] or "") != ("%s/%s" % spec).lower():
            return {"ok": False, "kind": "none", "err": "no matching npm package", "source": "osv", "data": None, "ms": None, "cached": False, "age": 0, "stale": False}
        a = fetch_task(ctx, None, spec, pkg, "osv_all")
        b = fetch_task(ctx, None, spec, pkg, "osv_latest", npm["data"]["version"])
        if not a["ok"]:
            return a
        if not b["ok"]:
            b = dict(a, data=None, ok=False, err=b["err"])
        return {"ok": True, "data": {"all": a["data"], "latest": b["data"]}, "ms": max(a["ms"] or 0, b["ms"] or 0), "cached": a["cached"] and b["cached"],
                "age": a["age"], "stale": a["stale"] or b["stale"], "err": a["err"], "kind": "ok", "source": "osv"}
    futs["osv"] = ex.submit(osv)
    out = {}
    for task, f in futs.items():
        left = max(0.1, ctx.t_end - time.time())
        try:
            out[task] = f.result(timeout=left)
        except Exception:
            out[task] = {"ok": False, "kind": "fail", "err": "timed out", "source": "osv" if task == "osv" else task.split("_")[0], "data": None, "ms": None, "cached": False, "age": 0, "stale": False}
    ex.shutdown(wait=False)
    out["_pkg"] = pkg
    out["_wall"] = int((time.time() - t0) * 1000)
    return out


# ------------------------------------------------------------------ the join, the score

def model(ctx, spec, pkg_override):
    r = gather(ctx, spec, pkg_override)
    g, rel, npm, wk, mo, hn, osv = (r[k] for k in ("gh_repo", "gh_releases", "npm_latest", "npm_week", "npm_month", "hn", "osv"))
    slug = ("%s/%s" % spec).lower()
    m = {"spec": "%s/%s" % spec, "raw": r, "pkg": r["_pkg"]}
    m["repo"] = g["data"] if g["ok"] else None
    m["releases"] = rel["data"] if rel["ok"] else None
    joined = npm["ok"] and npm["data"]["repo"] == slug
    m["npm"] = npm["data"] if joined else None
    m["npm_state"] = "joined" if joined else ("other-repo" if npm["ok"] else npm["kind"])
    m["npm_other"] = npm["data"]["repo"] if npm["ok"] and not joined else None
    m["week"] = wk["data"]["n"] if joined and wk["ok"] else None
    m["days"] = mo["data"]["days"] if joined and mo["ok"] else None
    m["hn"] = hn["data"] if hn["ok"] else None
    m["vulns_all"] = osv["data"]["all"] if osv["ok"] and osv["data"] else None
    m["vulns_open"] = osv["data"]["latest"] if osv["ok"] and osv["data"] else None
    m["now"] = ctx.now
    m["score"] = score(ctx.cfg, m)
    m["snap"] = snapshot(m)
    return m


def model_pair(ctx, specs):
    """The model for each (spec, package) at once: one pool per repo, all under the one deadline in ctx.t_end."""
    if len(specs) == 1:
        return [model(ctx, specs[0][0], specs[0][1])]
    with cf.ThreadPoolExecutor(max_workers=len(specs)) as ex:
        futs = [ex.submit(model, ctx, sp, pk) for sp, pk in specs]
        return [f.result() for f in futs]


def lerp(v, full, zero):
    if v <= full:
        return 100.0
    if v >= zero:
        return 0.0
    return 100.0 * (zero - v) / (zero - full)


def score(cfg, m):
    s, now = cfg["scoring"], m["now"]
    comp = {}
    if m["repo"] and m["repo"]["pushed"]:
        parts = [lerp((now - m["repo"]["pushed"]) / 86400.0, s["push_days_full"], s["push_days_zero"])]
        if m["releases"]:
            last = max((r["at"] for r in m["releases"] if r["at"]), default=None)
            if last:
                parts.append(lerp((now - last) / 86400.0, s["release_days_full"], s["release_days_zero"]))
        v = sum(parts) / len(parts)
        if m["repo"]["archived"] or (m["npm"] and m["npm"]["deprecated"]):
            v = min(v, s["capped_score"])
        comp["maintenance"] = v
    if m["vulns_open"] is not None:
        comp["security"] = max(0.0, 100.0 - sum(s["vuln_penalty"].get(v["sev"], s["vuln_penalty"]["UNKNOWN"]) for v in m["vulns_open"]))
    ad = []
    if m["repo"]:
        ad.append(min(100.0, 100.0 * math.log10(1 + m["repo"]["stars"]) / math.log10(1 + s["stars_full"])))
    if m["week"] is not None:
        ad.append(min(100.0, 100.0 * math.log10(1 + m["week"]) / math.log10(1 + s["downloads_full"])))
    if ad:
        comp["adoption"] = sum(ad) / len(ad)
    ch = trend_pct(m)
    if ch is not None:
        comp["momentum"] = max(0.0, min(100.0, 50.0 + s["momentum_gain_per_pct"] * ch))
    w = cfg["weights"]
    tot = sum(w[k] for k in comp)
    total = int(round(sum(comp[k] * w[k] for k in comp) / tot)) if tot else None
    v = None
    if total is not None:
        v = next(x for x in cfg["verdict"] if total >= x["min"])
    return {"parts": dict((k, int(round(x))) for k, x in comp.items()), "total": total, "verdict": v, "missing": [k for k in w if k not in comp]}


def trend_pct(m):
    d = m["days"]
    if not d or len(d) < 14:
        return None
    h = len(d) // 2
    a, b = sum(x for _, x in d[:h]), sum(x for _, x in d[h:])
    return None if a <= 0 else (b - a) * 100.0 / a


def valid_snap(d):
    if not isinstance(d, dict):
        return False
    ints = ("stars", "week", "score", "issues")
    if any(d.get(k) is not None and (isinstance(d.get(k), bool) or not isinstance(d.get(k), int)) for k in ints):
        return False
    if d.get("latest") is not None and not isinstance(d.get("latest"), str):
        return False
    return all(d.get(k) is None or (isinstance(d.get(k), list) and all(isinstance(x, str) for x in d[k])) for k in ("vulns", "hn"))


def valid_seen(v):
    """A saved 'seen' record from any older version: anything that is not exactly this shape is treated as no record."""
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
    return (isinstance(v, dict) and valid_snap(v.get("seen")) and num(v.get("seen_ts")) and (v.get("base") is None or valid_snap(v.get("base")))
            and (v.get("base_ts") is None or num(v.get("base_ts"))))


def snapshot(m):
    return {"stars": m["repo"]["stars"] if m["repo"] else None, "latest": (m["releases"] or [{}])[0].get("tag") if m["releases"] else None,
            "vulns": sorted(v["id"] for v in m["vulns_open"]) if m["vulns_open"] is not None else None, "week": m["week"],
            "hn": sorted(s["id"] for s in m["hn"]["stories"]) if m["hn"] else None, "score": m["score"]["total"], "issues": m["repo"]["issues"] if m["repo"] else None}


def diff_since(old, new):
    """Lines of (kind, old, new) for what changed. A field that was not read on either side is not a change."""
    ch = []
    def pair(label, a, b, fmt=str):
        if a is not None and b is not None and a != b:
            ch.append((label, fmt(a), fmt(b)))
    pair("latest release", old.get("latest"), new.get("latest"))
    pair("stars", old.get("stars"), new.get("stars"), lambda x: "{:,}".format(x))
    pair("open issues", old.get("issues"), new.get("issues"))
    pair("weekly downloads", old.get("week"), new.get("week"), lambda x: "{:,}".format(x))
    pair("health score", old.get("score"), new.get("score"))
    if old.get("vulns") is not None and new.get("vulns") is not None and old["vulns"] != new["vulns"]:
        ch.append(("open vulnerabilities", "%d (%s)" % (len(old["vulns"]), ", ".join(old["vulns"]) or "none"), "%d (%s)" % (len(new["vulns"]), ", ".join(new["vulns"]) or "none")))
    if old.get("hn") is not None and new.get("hn") is not None and set(new["hn"]) - set(old["hn"]):
        ch.append(("new discussion threads", str(len(old["hn"])), str(len(new["hn"]))))
    return ch


# ------------------------------------------------------------------ rows

def ago_days(now, t):
    return "unknown" if not t else ("today" if now - t < 86400 else "%s ago" % kit.fmt_duration(now - t))


def badges_row(ctx, m):
    cfg, r = ctx.cfg, m["raw"]
    groups = {"github": ("gh_repo", "gh_releases"), "npm": ("npm_latest", "npm_week", "npm_month"), "osv": ("osv",), "hn": ("hn",)}
    bs, bits = [], []
    for s, tasks in groups.items():
        rs = [r[t] for t in tasks]
        lab = cfg["sources"][s]["label"]
        if any(x["kind"] == "limited" for x in rs):
            tone, txt = "bad", "limit"
        elif s == "npm" and m["npm_state"] != "joined":
            tone, txt = "warn", "no match" if m["npm_state"] == "other-repo" else "none"
        elif s == "osv" and not r["osv"]["ok"] and r["osv"]["kind"] == "none":
            tone, txt = "warn", "skipped"
        elif any(not x["ok"] for x in rs):
            tone, txt = "bad", "down"
        elif any(x["stale"] for x in rs):
            tone, txt = "warn", "old copy"
        elif ctx.fixture:
            tone, txt = "ok", "sample"
        elif all(x["cached"] for x in rs):
            tone, txt = "ok", "cached"
        else:
            tone, txt = "ok", "%d ms" % max((x["ms"] or 0) for x in rs)
        if s == "github" and ctx.meta.get("github"):
            txt += " %s/%s left" % (ctx.meta["github"]["remaining"], ctx.meta["github"]["limit"])
        bs.append(("%s %s" % (lab, txt), tone))
        bits.append("%s %s" % (lab, txt))
    return kit.safe_row("Sources", " · ".join(bits) + " · all calls took %d ms together" % r["_wall"] if not ctx.fixture else " · ".join(bits), icon="network" if False else "Globe", badges=bs, copy=False)


def overview_rows(ctx, m, since, new_snapshot_note):
    cfg, now = ctx.cfg, m["now"]
    sc = m["score"]
    rows = []
    if ctx.fixture:
        rows.append(kit.safe_row("Sample data", "Recorded answers from 2026-11-15, no network. Set api.fixture_default to false in config.json for live data", icon="FileText", copy=False, badge="SAMPLE"))
    if sc["total"] is None:
        rows.append(kit.safe_row("Verdict: not enough data", "No source answered for %s" % m["spec"], icon="AlertCircle", badge="NO DATA", copy=False))
    else:
        p = sc["parts"]
        sub = " · ".join("%s %d" % (k.capitalize(), p[k]) for k in cfg["weights"] if k in p)
        if sc["missing"]:
            sub += " · not scored: " + ", ".join(sc["missing"])
        url = m["repo"]["url"] if m["repo"] and m["repo"]["url"] else "https://github.com/" + m["spec"]
        rows.append(kit.safe_row("%s · %d of 100" % (sc["verdict"]["label"], sc["total"]), sub, icon="CheckCircle2" if sc["total"] >= 80 else "AlertCircle",
                            badge=sc["verdict"]["badge"] if not sc["missing"] else "PARTIAL", tile=kit.tile("Health score", sc["total"], "/100", 100, note=sub[:80]),
                            open_url=pin_url(cfg, url) or None, copy="%s: %s, %d of 100" % (m["spec"], sc["verdict"]["label"], sc["total"])))
    rows.append(badges_row(ctx, m))
    g = ctx.meta.get("github")
    if m["raw"]["gh_repo"]["kind"] == "limited" or (g and g["remaining"].isdigit() and int(g["remaining"]) <= 5 and not ctx.token):
        rows.append(kit.safe_row("GitHub allows few requests without a token", "Optional and free: a token raises 60 an hour to 5,000. Enter for the setup line", icon="Key",
                            badge="OPTIONAL", copy=kit.setup_hint(APP, cfg["secret"]["name"])))
    if m["repo"]:
        r = m["repo"]
        rows.append(kit.safe_row("%s · %s stars" % (m["spec"], "{:,}".format(r["stars"])), "%s · %s%s" % (r["license"], r["description"][:80], " · ARCHIVED" if r["archived"] else ""), icon="Globe",
                            tile=kit.tile("Stars", r["stars"], "", None, note="%s forks" % "{:,}".format(r["forks"])), open_url=pin_url(cfg, r["url"] or "https://github.com/" + m["spec"]) or None, copy=m["spec"]))
        rows.append(kit.safe_row("Open issues · %d" % r["issues"], "includes open pull requests (GitHub counts both)", icon="List", tile=kit.tile("Open issues", r["issues"], "", None)))
    else:
        rows.append(kit.safe_row("GitHub: unavailable", m["raw"]["gh_repo"]["err"] or "no answer", icon="AlertCircle", badge="DOWN", copy=False))
    if since is not None:
        rows.append(kit.safe_row("Since you last looked · %s" % kit.fmt_count(len(since), "change"), new_snapshot_note if since else "nothing changed", icon="Clock", nav={"view": "since"}, copy=False))
    else:
        rows.append(kit.safe_row("Since you last looked", "first look at this repo: your next run shows the changes", icon="Clock", nav={"view": "since"}, copy=False))
    if m["releases"] is not None:
        n90 = sum(1 for x in m["releases"] if x["at"] and now - x["at"] < 90 * 86400)
        lt = m["releases"][0] if m["releases"] else None
        rows.append(kit.safe_row("Releases · %d in 90 days (of the newest %d)" % (n90, len(m["releases"])), ("latest %s, %s" % (lt["tag"], ago_days(now, lt["at"]))) if lt else "none published", icon="GitMerge", nav={"view": "releases"}, copy=False))
    else:
        rows.append(kit.safe_row("Releases · unavailable", m["raw"]["gh_releases"]["err"], icon="AlertCircle", nav={"view": "releases"}, copy=False))
    if m["week"] is not None:
        ch = trend_pct(m)
        rows.append(kit.safe_row("Downloads · %s a week" % kit.fmt_count(m["week"]), ("%s%.0f%% against the half-month before" % ("+" if ch >= 0 else "", ch)) if ch is not None else "npm package %s" % m["npm"]["name"],
                            icon="Download", nav={"view": "downloads"}, copy=False, tile=kit.tile("Weekly downloads", m["week"] / 1000.0, "k", None, note="npm %s" % m["npm"]["name"]),
                            trend=[x for _, x in (m["days"] or [])][-30:] or None))
    else:
        why = {"other-repo": ("package %s points at %s, not this repo: not used" % (m["pkg"], m["npm_other"])) if m["npm_other"] else "package %s does not name its repository: not used" % m["pkg"], "none": "no npm package named %s (add :name to the query)" % m["pkg"]}.get(m["npm_state"], "npm did not answer")
        rows.append(kit.safe_row("Downloads · not available", why, icon="Download", nav={"view": "downloads"}, copy=False))
    if m["vulns_open"] is not None:
        o, a = m["vulns_open"], m["vulns_all"] or []
        rows.append(kit.safe_row("Vulnerabilities · %d open" % len(o), "%d known in all versions; %d affect the latest" % (len(a), len(o)), icon="ShieldAlert" if o else "ShieldCheck", nav={"view": "vulns"}, copy=False,
                            tile=kit.tile("Open vulns", len(o), "", None, note="latest %s" % (m["npm"] or {}).get("version", "?")), badge="ATTENTION" if o else ""))
    else:
        rows.append(kit.safe_row("Vulnerabilities · unavailable", ("OSV: " + m["raw"]["osv"]["err"]) if m["raw"]["osv"]["err"] else "needs a matching npm package", icon="AlertCircle", nav={"view": "vulns"}, copy=False, badge="NOT CHECKED"))
    if m["hn"] is not None:
        top = max(m["hn"]["stories"], key=lambda s: s["points"], default=None)
        rows.append(kit.safe_row("Discussion · %d threads" % m["hn"]["total"], ("top: %s" % top["title"][:70]) if top else "none on Hacker News", icon="MessageSquare", nav={"view": "discussion"}, copy=False))
    else:
        rows.append(kit.safe_row("Discussion · unavailable", m["raw"]["hn"]["err"], icon="AlertCircle", nav={"view": "discussion"}, copy=False))
    rows.append(kit.refresh_row("overview", title="Check again", subtitle="Enter to fetch fresh data past the per-source cache"))
    return rows


def back():
    return kit.back_row("Back to the overview")


def stale_note(m, tasks):
    rs = [m["raw"][t] for t in tasks if m["raw"][t]["stale"]]
    return [kit.safe_row("Showing an old copy", "the source failed (%s); copy is %s old" % (rs[0]["err"], kit.fmt_duration(rs[0]["age"])), icon="Clock", badge="OLD COPY", copy=False)] if rs else []


def view_rows(ctx, view, m, since_info):
    now = m["now"]
    if view == "releases":
        rs = m["releases"]
        if not rs:
            return [back(), kit.safe_row("No releases", "none published or GitHub did not answer", icon="AlertCircle", copy=False)]
        out = [back()] + stale_note(m, ("gh_releases",))
        for i, x in enumerate(rs):
            prev = rs[i + 1]["body"] if i + 1 < len(rs) else ""
            out.append(kit.safe_row("%s · %s" % (x["tag"], ago_days(now, x["at"])), ((x["body"].splitlines() or [""])[0])[:80] or ("pre-release" if x["pre"] else "release"), icon="GitMerge",
                               open_url=pin_url(ctx.cfg, x["url"]) or None, multiline={"left": prev or "(no earlier release notes)", "right": x["body"] or "(no notes)"}, copy="%s %s" % (m["spec"], x["tag"])))
        return out
    if view == "vulns":
        if m["vulns_all"] is None:
            return [back(), kit.safe_row("Vulnerabilities unavailable", "OSV did not answer or no npm package matches this repo", icon="AlertCircle", copy=False)]
        openids = set(v["id"] for v in (m["vulns_open"] or []))
        out = [back()] + stale_note(m, ("osv",))
        for v in sorted(m["vulns_all"], key=lambda v: (v["id"] not in openids, -(v["published"] or 0))):
            st = "open in latest" if v["id"] in openids else "fixed before latest"
            out.append(kit.safe_row("%s · %s" % (v["id"], v["sev"].lower()), "%s · %s" % (v["summary"][:70], st), icon="ShieldAlert" if v["id"] in openids else "ShieldCheck",
                               open_url=pin_url(ctx.cfg, "https://osv.dev/vulnerability/" + urllib.parse.quote(v["id"], safe="")) or None, vid=v["id"], sev=v["sev"], status=st, fixed=", ".join(v["fixed"][:3]) or "no fixed version listed",
                               published=ago_days(now, v["published"]), cve=", ".join(v["cve"]) or "none", copy="%s %s" % (v["id"], v["summary"][:80])))
        return out if len(out) > 1 else out + [kit.safe_row("No known vulnerabilities", "OSV lists none for this package", icon="ShieldCheck", badge="CLEAR", copy=False)]
    if view == "downloads":
        d = m["days"]
        if not d:
            return [kit.safe_row("No download data", "needs a matching npm package", icon="AlertCircle", copy=False)]
        return [kit.safe_row("%s" % day, "{:,}".format(n), icon="Download", label=day[5:], value=n, copy=False) for day, n in d]
    if view == "discussion":
        h = m["hn"]
        if h is None:
            return [back(), kit.safe_row("Discussion unavailable", "Hacker News search did not answer", icon="AlertCircle", copy=False)]
        out = [back()] + stale_note(m, ("hn",))
        for s in sorted(h["stories"], key=lambda s: -s["points"]):
            out.append(kit.safe_row(s["title"][:100], "%d points · %d comments · %s" % (s["points"], s["comments"], ago_days(now, s["at"])), icon="MessageSquare", open_url=pin_url(ctx.cfg, s["url"]) or None,
                               points=s["points"], comments=s["comments"], posted=ago_days(now, s["at"]), copy=s["title"][:100]))
        return out if len(out) > 1 else out + [kit.safe_row("No threads", "no Hacker News story links to this repo", icon="MessageSquare", copy=False)]
    if view == "since":
        base, ch, base_ts = since_info
        if base is None:
            return [back(), kit.safe_row("First look", "Nothing to compare with yet. The next run after %d minutes shows what changed" % (ctx.cfg["snapshot_min_age_s"] // 60), icon="Clock", copy=False)]
        if not ch:
            return [back(), kit.safe_row("Nothing changed", "since %s ago" % kit.fmt_duration(now - base_ts), icon="CheckCircle2", copy=False)]
        left = "\n".join("%s: %s" % (l, a) for l, a, b in ch)
        right = "\n".join("%s: %s" % (l, b) for l, a, b in ch)
        out = [back(), kit.safe_row("All changes · %d" % len(ch), "since %s ago (the copy saved on your computer)" % kit.fmt_duration(now - base_ts), icon="Clock", multiline={"left": left, "right": right}, copy=False)]
        for l, a, b in ch:
            out.append(kit.safe_row("%s: %s to %s" % (l, a, b), "", icon="Activity", multiline={"left": "%s: %s" % (l, a), "right": "%s: %s" % (l, b)}))
        return out
    return []


def compare_rows(ctx, ms):
    a, b = ms
    def v(m, k):
        if k == "Health":
            return m["score"]["total"]
        if k == "Stars":
            return m["repo"]["stars"] if m["repo"] else None
        if k == "Downloads per week":
            return m["week"]
        if k == "Open vulns":
            return len(m["vulns_open"]) if m["vulns_open"] is not None else None
        if k == "Days since release":
            rs = [x["at"] for x in (m["releases"] or []) if x["at"]]
            return int((m["now"] - max(rs)) / 86400) if rs else None
        if k == "Days since push":
            return int((m["now"] - m["repo"]["pushed"]) / 86400) if m["repo"] and m["repo"]["pushed"] else None
        if k == "Open issues":
            return m["repo"]["issues"] if m["repo"] else None
    higher = {"Health": True, "Stars": True, "Downloads per week": True, "Open vulns": False, "Days since release": False, "Days since push": False, "Open issues": False}
    out = [back()]
    for k, hi in higher.items():
        x, y = v(a, k), v(b, k)
        lead = "not compared" if x is None or y is None else ("tie" if x == y else (a["spec"] if (x > y) == hi else b["spec"]))
        f = lambda z: "unknown" if z is None else "{:,}".format(z)
        out.append(kit.safe_row("%s: %s vs %s" % (k, f(x), f(y)), "leads: %s" % lead, icon="ArrowLeftRight", metric=k, first=f(x), second=f(y), lead=lead, copy=True))
    return out


def compare_overview(ctx, ms):
    a, b = ms
    rows = []
    if ctx.fixture:
        rows.append(kit.safe_row("Sample data", "Recorded answers from 2026-11-15, no network", icon="FileText", copy=False, badge="SAMPLE"))
    ta, tb = a["score"]["total"], b["score"]["total"]
    lead = "No clear leader" if ta is None or tb is None or ta == tb else "%s leads on health" % (a["spec"] if ta > tb else b["spec"])
    rows.append(kit.safe_row(lead, "%s %s vs %s %s" % (a["spec"], ta if ta is not None else "?", b["spec"], tb if tb is not None else "?"), icon="ArrowLeftRight", copy=True))
    for m in ms:
        sc = m["score"]
        rows.append(kit.safe_row("%s · %s" % (m["spec"], ("%d of 100" % sc["total"]) if sc["total"] is not None else "no data"), sc["verdict"]["label"] if sc["verdict"] else "not enough data", icon="Activity",
                            tile=kit.tile("Health", sc["total"], "/100", 100, note=m["spec"][:40]) if sc["total"] is not None else None, badge=sc["verdict"]["badge"] if sc["verdict"] else "",
                            open_url=pin_url(ctx.cfg, "https://github.com/" + m["spec"]) or None, copy=m["spec"]))
    rows.append(kit.safe_row("Side by side", "the metrics in a table", icon="List", nav={"view": "compare"}, copy=False))
    rows.append(kit.safe_row("Sources", " · ".join("%s %s" % (m["spec"], "ok" if m["repo"] else "GitHub down") for m in ms), icon="Globe", copy=False))
    rows.append(kit.refresh_row("overview", title="Check again", subtitle="Enter to fetch fresh data"))
    return rows


# ------------------------------------------------------------------ yaml

OVERVIEW_PANE = ["    overview:", "      right_widget:", "        kind: entity_preview", "        mode: selected_row", "        bind:", '          title: "{{row.title}}"', '          subtitle: "{{row.subtitle}}"',
                 "          tiles_above:", '            title: "{{row.kpi_label}}"', '            value: "{{row.kpi_value}}"', '            unit: "{{row.kpi_unit}}"', '            max: "{{row.kpi_max}}"', '            trend: "{{row.trend}}"',
                 '            subtitle: "{{row.kpi_note}}"', '            badge: "{{row.kpi_badge}}"', '          body: "{{row.body}}"']   # the overview is a list of rows that drill into views: each row is drawn by this preview, and the views keep their own widgets


def emit_yaml(cfg):
    app = cfg["app"]
    words = " ".join("{{scripts_dir}}/%s" % f for f in FILE_WORDS)
    cmd = "%s {{scripts_dir}}/" + _SELF + " {{view}} {{p1}} {{p2}} {{p3}} {{p4}} " + words
    ch = cfg["charts"]["downloads"]
    L = ["# Generated by: python3 scripts/" + _SELF + " --emit-yaml (edit config.json, not this file)", "schema_version: 1", "runtime: bridge", "id: %s" % app["id"], "chip: %s" % app["chip"],
         "title: %s" % json.dumps(app["title"]), "icon: %s" % app["icon"], "description: %s" % json.dumps(app["description"]),
         'placeholder_examples: ["expressjs/express", "fastify/fastify vs expressjs/express"]', "emits: Generic", "args:", '  - { name: view, from: "query.word(0)", default: overview }']
    for i in range(1, 5):
        L.append('  - { name: p%d, from: "query.word(%d)", default: "-" }' % (i, i))
    L += ["bridge:", "  command:"]
    for osn, py in (("macos", "python3"), ("linux", "python3"), ("windows", "python")):
        L.append('    %s: "%s"' % (osn, cmd % py))
    L += ["  parse: json", "  timeout_seconds: %d" % app["timeout"], "presentation:", "  widget: list", "  title_field: title", "  subtitle_field: subtitle", "  view_arg: view", "  right_widget:",
          "    kind: cards", "    mode: list_data", "    bind:", '      layout: "tiles"', '      title: "{{row.kpi_label}}"', '      value: "{{row.kpi_value}}"', '      unit: "{{row.kpi_unit}}"',
          '      max: "{{row.kpi_max}}"', '      trend: "{{row.trend}}"', '      subtitle: "{{row.kpi_note}}"', '      badge: "{{row.kpi_badge}}"', "  views:", *OVERVIEW_PANE]
    diff = ["      right_widget:", "        kind: diff", "        mode: selected_row", "        bind:", '          left: "{{row.left}}"', '          right: "{{row.right}}"']
    L += ["    releases:"] + diff + ['          leftLabel: "earlier"', '          rightLabel: "this release"']
    L += ["    since:"] + diff + ['          leftLabel: "last look"', '          rightLabel: "now"']
    L += ["    vulns:", "      right_widget:", "        kind: detail", "        mode: selected_row", "        bind:", '          title: "{{row.vid}}"', '          subtitle: "{{row.status}}"', "          fields:",
          '            - { label: Severity, value: "{{row.sev}}" }', '            - { label: Status, value: "{{row.status}}" }', '            - { label: Fixed in, value: "{{row.fixed}}" }',
          '            - { label: Published, value: "{{row.published}}" }', '            - { label: CVE, value: "{{row.cve}}", copy: true }']
    L += ["    downloads:", "      right_widget:", "        kind: chart", "        mode: list_data", "        bind:", '          type: "%s"' % ch["type"], '          x: "label"', '          y: "value"', "          label: %s" % json.dumps(ch["title"])]
    L += ["    discussion:", "      right_widget:", "        kind: detail", "        mode: selected_row", "        bind:", '          title: "{{row.title}}"', '          subtitle: "{{row.posted}}"', "          fields:",
          '            - { label: Points, value: "{{row.points}}" }', '            - { label: Comments, value: "{{row.comments}}" }', '            - { label: Posted, value: "{{row.posted}}" }']
    L += ["    compare:", "      right_widget:", "        kind: table", "        mode: list_data", "        bind:", "          columns:", "            - { field: metric, label: Metric }",
          "            - { field: first, label: First, align: right }", "            - { field: second, label: Second, align: right }", "            - { field: lead, label: Leads }"]
    L += ["actions:", '  - { id: open, kind: url, target: row, label: Open, url_template: "{{row.open_url}}" }', '  - { id: copy, kind: composer, target: row, label: Copy, insert: "{{row.copy_text}}" }']
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ main

def parse_specs(words):
    """owner/repo[:npm-package] [vs owner/repo[:npm-package]]. Returns (specs, error)."""
    specs, i = [], 0
    toks = [w for w in words]
    if len(toks) == 3 and toks[1].lower() == "vs":
        toks = [toks[0], toks[2]]
    if not toks or len(toks) > 2:
        return None, "Type owner/repo, or: owner/repo vs owner/repo"
    for t in toks:
        m = SPEC.match(t)
        if m and (set(m.group(1)) <= {"."} or set(m.group(2)) <= {"."}):
            m = None
        if not m:
            return None, "%s is not owner/repo (letters, digits, dots, dashes, underscores; add :package for the npm name)" % kit.clean_text(t, 40)
        specs.append(((m.group(1), m.group(2)), m.group(3)))
    return specs, None


def main(argv):
    global APP
    cfg = load_json("config.json")
    APP = cfg["app"]["id"]   # a copy with a new id gets its own caches and its own key name
    if "--emit-yaml" in argv:
        sys.stdout.write(emit_yaml(cfg))
        return
    record = None
    args = split_args(argv)
    if "--record" in args:
        record, args = True, [a for a in args if a != "--record"]
    view = "overview"
    if args and args[0] in VIEWS:
        view, args = args[0], args[1:]
    demos = [a for a in args if a in DEMOS]
    force = "refresh" in args
    args = [a for a in args if a not in DEMOS and a != "refresh"]
    lastc = kit.Cache(APP, 86400, shape=lambda v: isinstance(v, dict) and isinstance(v.get("words"), list), root=kit.cache.default_root(APP) + "/last")
    if not args:
        last = lastc.get("last")
        if not last:
            kit.emit([kit.safe_row("Type owner/repo", "for example: =repo-radar expressjs/express   or   =repo-radar fastify/fastify vs expressjs/express", icon="Activity", copy=False)])
        args = last["words"]
    specs, err = parse_specs(args)
    if err:
        kit.emit([kit.error_row(err, title="Not run: that input is not allowed")])
    fixture = bool(cfg["api"]["fixture_default"]) if os.environ.get("BOLT_APP_FIXTURE") not in ("0", "1") else os.environ["BOLT_APP_FIXTURE"] == "1"
    fx = load_json("fixtures.json") if fixture else {}
    if record:
        fixture = False
    tok = kit.get_secret(APP, cfg["secret"]["name"]) if not fixture else kit.Secret()
    now = fx.get("_now") if fixture else time.time()
    ctx = Ctx(cfg, fx, fixture, tok.value if tok else None, now, force, record, demos)
    if fixture:
        have = sorted(fx.get("repos", {}))
        for (o, r), _ in specs:
            if ("%s/%s" % (o, r)) not in have:
                kit.emit([kit.error_row("Sample mode knows only: %s. Set api.fixture_default to false for live data" % ", ".join(have), title="Not in the recorded sample")])
    ms = model_pair(ctx, specs)
    for (spec, pk), m in zip(specs, ms):
        if m["raw"]["gh_repo"]["kind"] == "none" and not fixture:
            kit.emit([kit.error_row("GitHub has no repository %s/%s" % spec, title="No such repository")])
    if record:
        key = "%s/%s" % specs[0][0]
        print(json.dumps({key: dict(ctx.recorded, _headers=ctx.meta.get("github", {}))}))
        return
    lastc.put("last", {"words": args})
    m0 = ms[0]
    since = None
    if len(ms) == 1:
        sc = kit.Cache(APP, 90 * 86400, shape=valid_seen, root=kit.cache.default_root(APP) + "/seen")
        key = m0["spec"].lower()
        rec = sc.get(key) if not fixture else (fx.get("seen", {}).get(key) if valid_seen(fx.get("seen", {}).get(key)) else None)
        base = base_ts = None
        if rec:
            if m0["now"] - rec["seen_ts"] >= cfg["snapshot_min_age_s"]:
                base, base_ts = rec["seen"], rec["seen_ts"]
            else:
                base, base_ts = rec.get("base"), rec.get("base_ts")
        if not fixture and not record:
            sc.put(key, {"base": base, "base_ts": base_ts, "seen": m0["snap"], "seen_ts": m0["now"]} if rec is None or m0["now"] - rec["seen_ts"] >= cfg["snapshot_min_age_s"] else dict(rec, seen=m0["snap"]))
        ch = diff_since(base, m0["snap"]) if base else None
        since = ch
        since_info = (base, ch, base_ts)
    if len(ms) == 2:
        out = compare_rows(ctx, ms) if view == "compare" else compare_overview(ctx, ms)
    elif view == "overview":
        note = "%s since %s ago" % (", ".join(c[0] for c in since[:3]), kit.fmt_duration(m0["now"] - since_info[2])) if since else ""
        out = overview_rows(ctx, m0, since, note)
    else:
        out = view_rows(ctx, view, m0, since_info) or [back()]
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
