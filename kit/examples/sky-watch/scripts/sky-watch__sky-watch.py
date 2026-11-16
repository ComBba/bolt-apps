#!/usr/bin/env python3
"""=sky-watch [iss | launches | quakes | <city> | demo]: space and sky from five free public sources, no key.

An example of the Bolt Apps kit for several independent sources in one app: the ISS position (api.wheretheiss.at), the next launches
(ll.thespacedevs.com, rate limited: cached 10 minutes), earthquakes of magnitude 4.5 and up in the last day (earthquake.usgs.gov) and, when
a city is typed, its weather and sunrise and sunset (geocoding-api.open-meteo.com, api.open-meteo.com). Every request is https to a host in
config.json, follows redirects only on the same host, sends no cookies or credentials, has a timeout and a 1 MB cap, and typed text is only
percent-encoded into the query. Rows go through the kit (text safety, row contract). `demo` shows recorded sample answers, labelled."""
import concurrent.futures as cf
import http.client
import json
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
VIEWS = ("overview", "iss", "launches", "quakes", "weather")
APP = "sky-watch"
SAFETY = "Public data, shown as is."
WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
       71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers", 81: "rain showers", 82: "heavy showers", 95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"}


def load_json(name):
    with open(os.path.join(HERE, _PFX + name), "r", encoding="utf-8") as f:
        return json.load(f)


def split_args(argv):
    a = list(argv[1:])
    if len(a) >= 3 and [os.path.basename(x) for x in a[-3:]] == list(FILE_WORDS):
        a = a[:-3]
    return [w for w in a if w != "-"]


# ------------------------------------------------------------------ the network: https, fixed hosts, same-host redirects, no credentials, timeout, size cap

class Fail(Exception):
    pass


class _Redirects(urllib.request.HTTPRedirectHandler):
    hosts = ()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlparse(newurl)
        if u.scheme != "https" or u.port not in (None, 443) or u.hostname != urllib.parse.urlparse(req.full_url).hostname or u.hostname not in self.hosts:
            raise Fail("redirected to another host: not followed")
        return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)


def fetch(cfg, url, budget):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.port not in (None, 443) or u.hostname not in cfg["hosts"]:
        raise Fail("host not allowed")
    _Redirects.hosts = tuple(cfg["hosts"])
    req = urllib.request.Request(url, headers={"User-Agent": cfg["api"]["user_agent"], "Accept": "application/json"})   # no cookies, no Authorization
    try:
        with urllib.request.build_opener(_Redirects).open(req, timeout=max(1.0, min(cfg["api"]["call_timeout_s"], budget))) as r:
            raw = r.read(cfg["api"]["max_bytes"] + 1)
    except urllib.error.HTTPError as e:
        raise Fail("rate limited" if e.code == 429 else "answered %d" % e.code)
    except http.client.HTTPException:   # IncompleteRead, BadStatusLine and the like: one flaky source never kills the overview
        raise Fail("the answer was cut short")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Fail("timed out" if "timed out" in str(e) else "could not connect")
    if len(raw) > cfg["api"]["max_bytes"]:
        raise Fail("answer too large")
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        raise Fail("answer was not JSON")


# ------------------------------------------------------------------ one source: fresh cache, then the network, then an old copy

class Ctx(object):
    def __init__(self, cfg, fx, fixture, now, force):
        self.cfg, self.fx, self.fixture, self.now, self.force = cfg, fx, fixture, now, force
        self.deadline = time.time() + cfg["api"]["total_budget_s"]
        self.caches = {}
        self.old = {}

    def cache(self, name, ttl):
        if name not in self.caches:
            self.caches[name] = kit.Cache(APP + "-" + name, ttl, shape=lambda v: isinstance(v, dict))
            self.old[name] = kit.Cache(APP + "-" + name + "-old", 86400, shape=lambda v: isinstance(v, dict))
        return self.caches[name]


def num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) < 1e15 else None


def source(ctx, name, query=""):
    """(data, note): data is the parsed answer or None; note says why it is old or missing. Sample mode reads the recorded answer, never the network."""
    if ctx.fixture:
        d = ctx.fx.get(name)
        d = d.get(query.lower()) if name == "geocode" and isinstance(d, dict) else d
        return (d, "") if d is not None else (None, "not in the recorded sample")
    src = ctx.cfg["sources"][name]
    ck = name + ":" + query.lower()
    c = ctx.cache(name, src["ttl"])
    if not ctx.force:
        hit = c.get(ck)
        if hit is not None:
            return hit["d"], ""
    url = src["url"]
    if name == "geocode":
        url += urllib.parse.quote(query, safe="")   # typed text is only percent-encoded, into the query
    elif name == "weather":
        la, lo = (float(x) for x in query.split(","))
        url += "&latitude=%.4f&longitude=%.4f" % (la, lo)
    try:
        d = fetch(ctx.cfg, url, ctx.deadline - time.time())
        if not isinstance(d, dict):
            raise Fail("answer was not an object")
        c.put(ck, {"d": d})
        ctx.old[name].put(ck, {"d": d})
        return d, ""
    except Fail as e:
        old = ctx.old[name].get(ck)
        if old is not None:
            return old["d"], "showing an old copy: %s" % e
        return None, str(e)


# ------------------------------------------------------------------ rows: one pane shape for all (SOURCE, WHEN, KEY FIGURE, DATA)

def when(ctx, ts):
    t = num(ts)
    if t is None:
        return "unknown"
    s = ctx.now - t
    if -10 < s < 0:   # a clock a few seconds apart is not "in 3 s"
        return "just now"
    return ("%s ago" % kit.fmt_duration(s)) if s >= 0 else ("in %s" % kit.fmt_duration(-s))


def iso_ts(s):
    m = re.match(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)", str(s or ""))
    if not m:
        return None
    import calendar
    return calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0))


def srow(title, subtitle, source, when_, key, data, url=None, icon="globe", nav=None, tile=None, copy=None, **kw):
    body = "**%s**\n\n- Source: %s\n- When: %s\n- Key figure: %s\n- Data: %s\n\n%s" % (kit.clean_text(title, 80), source, when_, key, data, SAFETY)
    return kit.safe_row(title, subtitle, icon=icon, body=body, nav=nav, tile=tile, open_url=url or None, url=url or None,
                        copy=copy or ("%s: %s (%s, %s)" % (title, key, source, when_)), sw_source=source, sw_when=when_, sw_key=key, sw_data=data, **kw)


def back():
    return kit.back_row("Back to the sky now")


def iss_row(ctx, d, note, nav=True):
    lat, lon, alt, vel = num(d.get("latitude")), num(d.get("longitude")), num(d.get("altitude")), num(d.get("velocity"))
    if None in (lat, lon, alt, vel):
        raise Fail("unexpected answer")
    key = "%s km up, %s km/h" % (kit.fmt_num(alt, 0), kit.fmt_num(vel, 0))
    return srow("International Space Station", "%s, %s · %s" % (kit.fmt_num(lat, 2), kit.fmt_num(lon, 2), key), "api.wheretheiss.at", when(ctx, d.get("timestamp")), key,
                "lat %.2f, lon %.2f, %s" % (lat, lon, kit.clean_text(str(d.get("visibility", "")), 20) or "visibility unknown"),
                url="https://www.openstreetmap.org/?mlat=%.4f&mlon=%.4f#map=3/%.2f/%.2f" % (lat, lon, lat, lon), icon="globe",
                nav={"view": "iss"} if nav else None, tile=kit.tile("Altitude", alt, "km", None, note=note or "now"))


def text_of(*vals):
    """The first non-empty text among strings or {name: text} dicts (the list shape of Launch Library 2 has flat strings, the detail shape has objects)."""
    for v in vals:
        if isinstance(v, dict):
            v = v.get("name")
        if isinstance(v, str) and v.strip():
            return kit.clean_text(v, 60)
    return ""


DONE = ("failure", "success", "partial failure")


def upcoming(ctx, d):
    """The launches still to come: not before now, and not already a success or failure (the upcoming list can hold one that just flew)."""
    out = []
    for x in (d.get("results") or []):
        if not isinstance(x, dict):
            continue
        net = iso_ts(x.get("net"))
        st = text_of((x.get("status") or {}).get("abbrev") if isinstance(x.get("status"), dict) else None, x.get("status")).lower()
        if net is not None and net < ctx.now or st in DONE:
            continue
        out.append(x)
    return out


def launch_rows(ctx, d, limit):
    out = []
    for x in upcoming(ctx, d)[:limit]:
        net = iso_ts(x.get("net"))
        pad_obj = x.get("pad") if isinstance(x.get("pad"), dict) else {}
        pad = text_of(x.get("pad") if isinstance(x.get("pad"), str) else pad_obj.get("name"))
        loc = text_of(x.get("location") if isinstance(x.get("location"), str) else None, (pad_obj.get("location") or {}) if isinstance(pad_obj.get("location"), dict) else None)
        lsp = text_of(x.get("lsp_name"), x.get("launch_service_provider"))
        mission = text_of(x.get("mission"), x.get("mission_name"))
        status = text_of(x.get("status"))
        key = "NET %s" % kit.clean_text(str(x.get("net", ""))[:16].replace("T", " "), 20)
        data = ", ".join(s for s in (status, mission, pad, loc) if s) or "no more detail listed"
        url = x.get("url") if str(x.get("url", "")).startswith("https://ll.thespacedevs.com/") else None
        out.append(srow(text_of(x.get("name")) or "Launch", " · ".join(s for s in (key, lsp) if s), "ll.thespacedevs.com", when(ctx, net), key, data, url=url, icon="Zap"))
    return out


def quake_rows(ctx, d, limit):
    out = []
    for f in (d.get("features") or [])[:limit]:
        p = (f or {}).get("properties") or {}
        mag = num(p.get("mag"))
        if mag is None:
            continue
        t = num(p.get("time"))
        key = "M%.1f" % mag
        depth = num(((f.get("geometry") or {}).get("coordinates") or [None, None, None])[2])
        url = p.get("url") if str(p.get("url", "")).startswith("https://earthquake.usgs.gov/") else None
        out.append(srow(kit.clean_text(str(p.get("place", "Earthquake")), 80), "%s · %s" % (key, when(ctx, t / 1000.0 if t else None)), "earthquake.usgs.gov", when(ctx, t / 1000.0 if t else None), key,
                        "magnitude %.1f%s" % (mag, (", depth %s km" % kit.fmt_num(depth, 0)) if depth is not None else ""), url=url, icon="Activity", tile=kit.tile("Magnitude", mag, "", 10, note="USGS")))
    return out


def weather_rows(ctx, city, g, w):
    r = ((g or {}).get("results") or [None])[0]
    if not isinstance(r, dict) or num(r.get("latitude")) is None:
        return None
    place = ", ".join(x for x in (kit.clean_text(str(r.get("name", city)), 40), kit.clean_text(str(r.get("country", "")), 40)) if x)
    cur, daily = (w or {}).get("current") or {}, (w or {}).get("daily") or {}
    temp, wind = num(cur.get("temperature_2m")), num(cur.get("wind_speed_10m"))
    out = []
    if temp is not None:
        key = "%s °C, %s" % (kit.fmt_num(temp, 1), WMO.get(int(num(cur.get("weather_code")) or 0), "weather code %s" % cur.get("weather_code")))
        out.append(srow("Weather in %s" % place, key, "api.open-meteo.com", kit.clean_text(str(cur.get("time", "now")).replace("T", " "), 20), key, "wind %s km/h" % kit.fmt_num(wind, 0) if wind is not None else "wind unknown",
                        url="https://open-meteo.com/en/docs", icon="CloudSun", tile=kit.tile("Temperature", temp, "°C", None, note=place)))
    sr, ss = (daily.get("sunrise") or [None])[0], (daily.get("sunset") or [None])[0]
    if sr and ss:
        key = "sunrise %s, sunset %s" % (str(sr)[11:16], str(ss)[11:16])
        out.append(srow("Sunrise and sunset in %s" % place, key, "api.open-meteo.com", str(sr)[:10], key, "local time, zone %s" % kit.clean_text(str((w or {}).get("timezone", "")), 40), icon="cloud-sun"))
    return out or None


def old_note(row, note):
    """Say a copy is old on the row itself (subtitle, badge and pane body), whatever kind of row it is."""
    if note and "old copy" in note:
        row["subtitle"] = (kit.clean_text(row.get("subtitle", ""), 120) + " · old copy").strip(" ·")
        row["badge"] = "OLD COPY"
        row["kpi_badge"] = "OLD COPY" if row.get("kpi_value") not in (None, "") else row.get("kpi_badge", "")
        row["body"] = "**Old copy:** %s.\n\n%s" % (note, row.get("body", ""))
        row["sw_when"] = (row.get("sw_when", "") + " (old copy)").strip()
    return row


def old_rows(rows, note):
    return [old_note(r, note) for r in rows]


def label(rows):
    return [kit.row("SAMPLE DATA: recorded answers, not live", "Run =sky-watch with no word for the live sky", body="Sample data: these answers were recorded for the example. Type =sky-watch for live data.", icon="FileText", copy=False, badge="SAMPLE")] + rows


def fail_row(name, why):
    return kit.row("%s unavailable" % name, "%s. Enter to try again" % why, icon="AlertCircle", badge="OFFLINE", body="%s did not answer (%s)." % (name, why), copy=False)


def hint_row():
    return kit.row("Weather and sunrise", "Type a city: =sky-watch Paris", icon="CloudSun", nav=None, body="Type =sky-watch and a city name for its weather and sunrise and sunset.", copy=False)


# ------------------------------------------------------------------ views

def overview(ctx):
    names = ("iss", "launches", "quakes")
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        res = dict(zip(names, ex.map(lambda n: source(ctx, n), names)))
    rows, lim = [], ctx.cfg["limits"]
    d, note = res["iss"]
    rows.append(old_note(iss_row(ctx, d, note), note) if d else fail_row("Space Station position", note))
    d, note = res["launches"]
    first = launch_rows(ctx, d, 1) if d else []
    if first:
        net = iso_ts(upcoming(ctx, d)[0].get("net"))
        rows.append(old_note(next_launch(ctx, first[0], (net - ctx.now) / 86400.0 if net else None), note))
    else:
        rows.append(fail_row("Launches", note or "no upcoming launches listed"))
    d, note = res["quakes"]
    qs = quake_rows(ctx, d, lim["quakes"]) if d else []
    rows.append(old_note(srow("Earthquakes M4.5+ in the last day: %d" % len(qs) if qs else "Earthquakes", "%s listed · the biggest first below" % kit.fmt_count(len(qs), "quake", "quakes"), "earthquake.usgs.gov", "last 24 hours",
                     "%s M4.5+" % kit.fmt_count(len(qs), "quake", "quakes"), "from the USGS summary feed", url="https://earthquake.usgs.gov/earthquakes/map/", icon="Activity", nav={"view": "quakes"},
                     tile=kit.tile("M4.5+ quakes", len(qs), "", None, note="last 24 h")), note) if d else fail_row("Earthquakes", note))
    rows.append(hint_row())
    return rows


def next_launch(ctx, r, days):
    r["nav"] = {"view": "launches"}
    if days is not None and days >= 0:
        r.update({"kpi_label": "Days to next launch", "kpi_value": round(days, 1), "kpi_unit": "d", "kpi_max": "", "kpi_note": "NET", "kpi_foot": "", "kpi_badge": ""})
    return r


def run_view(ctx, view, text):
    lim = ctx.cfg["limits"]
    if view == "overview":
        return overview(ctx)
    if view == "iss":
        d, note = source(ctx, "iss")
        return [back()] + ([old_note(iss_row(ctx, d, note, nav=False), note)] if d else [fail_row("Space Station position", note)])
    if view == "launches":
        d, note = source(ctx, "launches")
        rows = launch_rows(ctx, d, lim["launches"]) if d else []
        return [back()] + (old_rows(rows, note) or [fail_row("Launches", note or "no upcoming launches listed")])
    if view == "quakes":
        d, note = source(ctx, "quakes")
        rows = quake_rows(ctx, d, lim["quakes"]) if d else []
        return [back()] + (old_rows(rows, note) or [fail_row("Earthquakes", note or "no quakes of magnitude 4.5 or more in the last day")])
    g, gnote = source(ctx, "geocode", text)
    if not g or not (g.get("results") or []):
        return [back(), kit.row("No such place", "Try another city name", icon="Search", body="The place finder knew no city called %s." % kit.clean_text(text, 40), copy=False)] if g is not None else [back(), fail_row("Place finder", gnote)]
    r = g["results"][0]
    lat, lon = num(r.get("latitude")), num(r.get("longitude"))
    if lat is None or lon is None:
        return [back(), fail_row("Place finder", "unexpected answer")]
    w, wnote = source(ctx, "weather", "%.4f,%.4f" % (lat, lon))
    rows = weather_rows(ctx, text, g, w) if w else None
    return [back()] + (old_rows(rows, " ".join(n for n in (gnote, wnote) if n)) if rows else [fail_row("Weather", wnote or "unexpected answer")])


def emit_yaml(cfg):
    app = cfg["app"]
    words = " ".join("{{scripts_dir}}/%s" % f for f in FILE_WORDS)
    pane = ["        kind: entity_preview", "        mode: selected_row", "        bind:", '          title: "{{row.title}}"', '          subtitle: "{{row.subtitle}}"', "          tiles_above:", '            title: "{{row.kpi_label}}"',
            '            value: "{{row.kpi_value}}"', '            unit: "{{row.kpi_unit}}"', '            max: "{{row.kpi_max}}"', '            subtitle: "{{row.kpi_note}}"', '            badge: "{{row.kpi_badge}}"',
            "          fields:", '            - { label: SOURCE, value: "{{row.sw_source}}" }', '            - { label: WHEN, value: "{{row.sw_when}}" }', '            - { label: KEY FIGURE, value: "{{row.sw_key}}" }',
            '            - { label: DATA, value: "{{row.sw_data}}" }', '          body: "{{row.body}}"', "          actions:", '            - "open"', '            - "copy"']
    L = ["# Generated by: python3 scripts/" + _SELF + " --emit-yaml (edit config.json, not this file)", "schema_version: 1", "runtime: bridge", "id: %s" % app["id"], "chip: %s" % app["chip"],
         "title: %s" % json.dumps(app["title"]), "icon: %s" % app["icon"], "description: %s" % json.dumps(app["description"]),
         "placeholder_examples: %s" % json.dumps(app["placeholder_examples"]), "emits: Generic", "args:", '  - { name: view, from: "query.word(0)", default: overview }']
    for i in range(1, 4):
        L.append('  - { name: p%d, from: "query.word(%d)", default: "-" }' % (i, i))
    L += ["bridge:", "  command:"]
    for osn in ("macos", "linux"):
        L.append('    %s: "python3 {{scripts_dir}}/%s {{view}} {{p1}} {{p2}} {{p3}} %s"' % (osn, _SELF, words))
    L += ["  parse: json", "  timeout_seconds: %d" % app["timeout"], "presentation:", "  widget: list", "  title_field: title", "  subtitle_field: subtitle", "  view_arg: view", "  right_widget:"] + [l[4:] for l in pane] + ["  views:"]
    for v in VIEWS:
        L += ["    %s:" % v, "      right_widget:"] + pane
    L += ["actions:", '  - { id: open, kind: url, target: row, label: "Open source", url_template: "{{row.open_url}}" }', '  - { id: copy, kind: composer, target: row, label: "Copy summary", insert: "{{row.copy_text}}" }']
    return "\n".join(L) + "\n"


def main(argv):
    global APP
    cfg = load_json("config.json")
    APP = cfg["app"]["id"]
    if "--emit-yaml" in argv:
        sys.stdout.write(emit_yaml(cfg))
        return
    args = split_args(argv)
    force = "refresh" in args
    args = [a for a in args if a != "refresh"]
    demo = bool(args) and args[0].lower() == "demo"
    if demo:
        args = args[1:]
    view = "overview"
    if args and args[0].lower() in VIEWS:
        view, args = args[0].lower(), args[1:]
    elif args:
        view = "weather"   # a first word that is not a view is a city
    text = kit.clean_text(" ".join(args), 80) if view == "weather" else ""
    env = os.environ.get("BOLT_APP_FIXTURE")
    fixture = demo or ((env == "1") if env in ("0", "1") else bool(cfg["api"]["fixture_default"]))
    if view == "weather" and len(text) < 2:
        kit.emit([back(), kit.row("Type a city", "for example: =sky-watch Paris", icon="Search", body="Type =sky-watch and a city name.", copy=False)])
    fx = load_json("fixtures.json") if fixture else {}
    ctx = Ctx(cfg, fx, fixture, fx.get("_now") if fixture else time.time(), force)
    rows = run_view(ctx, view, text)
    kit.emit(label(rows) if demo else rows)


def run(argv):
    try:
        main(argv)
    except SystemExit:
        raise
    except kit.KitError as e:
        kit.emit([kit.error_row("Row contract: %s" % kit.clean_text(str(e), 200), title="This app could not run")])
    except Exception as e:   # one plain row: never a traceback
        if os.environ.get("BOLT_APP_DEBUG"):
            import traceback
            traceback.print_exc()
        kit.emit([kit.error_row("%s while building the rows. Run the script in a terminal to see why." % e.__class__.__name__)])


if __name__ == "__main__":
    run(sys.argv)
