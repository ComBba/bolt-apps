"""Shared engine: a large answer keeps an old copy (the cache holds the rows as read, cut to the fields config.json names) and an answer
over the read limit says it is too large; the steps of a lookup chain share one deadline. Runs on Python 3.9."""
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_cold_run_engine import cfg_of, fixtures_of, EX  # noqa: E402


def tickets(n, used=0, unused=0):
    """n tickets; `used` pads the summary (a field a row shows), `unused` adds a field no template reads."""
    out = []
    for i in range(n):
        t = {"id": "TK-%d" % i, "summary": "Ticket %d %s" % (i, "s" * used), "state": "open", "priority": 1, "projectId": "P-1", "assignee": {"name": "A"}}
        if unused:
            t["raw_html"] = "u" * unused
        out.append(t)
    return {"data": out}


class Server(http.server.BaseHTTPRequestHandler):
    """Answers by the last path segment: Server.status[name] is an HTTP status, Server.payload[name] the answer (default the sample answer)."""
    status = {}
    payload = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        name = self.path.split("?")[0].strip("/").split("/")[-1]
        code = Server.status.get(name, 200)
        body = json.dumps(Server.payload.get(name, {}) if code == 200 else {"message": "server error"}).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass   # the engine stops reading an answer that is too large


class LiveBase(unittest.TestCase):
    """The portal template against a loopback server with a key; HOME is the app folder, so the cache lives there between runs."""
    app = "portal-template"
    key = "abcdef123456"

    def setUp(self):
        self.srv = http.server.ThreadingHTTPServer(("localhost", 0), Server)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        Server.status = {}
        Server.payload = fixtures_of(self.app)
        self.cfg = cfg_of(self.app)
        self.cfg["api"].update({"base_url": "http://localhost:%d" % self.srv.server_address[1], "fixture_default": False, "on_missing_key": "setup"})
        self.dirs = []

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def folder(self):
        d = tempfile.mkdtemp()
        self.dirs.append(d)
        scripts = os.path.join(EX, self.app, "scripts")
        for f in os.listdir(scripts):
            if f.endswith((".py", ".json")):
                shutil.copy(os.path.join(scripts, f), os.path.join(d, f))
        with open(os.path.join(d, self.app + "__config.json"), "w") as f:
            json.dump(self.cfg, f)
        return d

    def run_engine(self, args, d, env=None):
        e = dict(os.environ)
        e.pop("BOLT_APP_FIXTURE", None)
        e.update({"HOME": d, "PYTHONDONTWRITEBYTECODE": "1", "BOLT_APP_FIXTURE": "0", "EXAMPLE_API_KEY": self.key})
        e.update(env or {})
        return subprocess.run([sys.executable, os.path.join(d, self.app + "__engine.py")] + args, env=e, capture_output=True, text=True, cwd=d)

    def rows(self, args, d=None, env=None):
        r = self.run_engine(args, d or self.folder(), env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class LargeAnswers(LiveBase):
    def test_an_answer_over_1_mb_keeps_an_old_copy_when_its_rows_fit(self):
        Server.payload = dict(Server.payload, tickets=tickets(1500, unused=1000))   # about 1.7 MB, the rows a view reads are far smaller
        d = self.folder()
        self.assertEqual(self.rows(["tickets"], d)[0]["subtitle"], "1500 tickets, showing the first 50")
        Server.status = {"account": 503, "tickets": 503}
        rows = self.rows(["tickets", "refresh"], d)
        text = json.dumps(rows)
        self.assertIn("is not answering. Showing data from", text, "the old copy is shown")
        self.assertEqual(rows[0]["subtitle"], "1500 tickets, showing the first 50")
        self.assertNotIn("Could not read tickets", text)

    def test_rows_from_the_cache_are_the_rows_from_the_answer(self):
        Server.payload = dict(Server.payload, tickets=dict(tickets(40, unused=50), data=fixtures_of(self.app)["tickets"]["data"] + tickets(40, unused=50)["data"]))
        for args in (["overview"], ["tickets"], ["tickets", "open"], ["projects"], ["projects", "P-1"]):
            d = self.folder()
            first = self.rows(args, d)    # the answer (and the cache is filled)
            again = self.rows(args, d)    # the cache, inside its ttl
            self.assertGreater(len(first), 3, args)
            no_age = lambda rows: [r for r in rows if r.get("kpi_badge") != "CACHED"]   # noqa: E731  (drawn only once the copy is 2 s old)
            self.assertEqual(no_age(again), no_age(first), args)

    def test_no_old_copy_says_the_last_answer_was_too_large_to_keep(self):
        Server.payload = dict(Server.payload, tickets=tickets(6000, used=200))   # the rows themselves are about 1.5 MB
        d = self.folder()
        self.rows(["tickets"], d)
        Server.status = {"account": 503, "tickets": 503}
        rows = self.rows(["tickets", "refresh"], d)
        notice = [r for r in rows if r["title"] == "Some data did not load: tickets"]
        self.assertEqual(len(notice), 1, json.dumps(rows)[:400])
        self.assertIn("No old copy of tickets: its last answer was over 1 MB", notice[0]["subtitle"])

    def test_an_answer_over_5_mb_is_too_large_not_an_error(self):
        Server.payload = dict(Server.payload, tickets=tickets(25000, used=200))   # about 6.2 MB
        rows = self.rows(["tickets"])
        text = json.dumps(rows)
        self.assertIn("Example Service sent more than 5 MB, more than this app reads", text)
        self.assertNotIn("returned an error", text)
        self.assertIn("Could not read tickets", text)

    def test_a_copy_kept_under_another_config_is_not_used(self):
        d = self.folder()
        self.rows(["tickets"], d)
        self.cfg["endpoints"]["tickets"]["map"]["title"] = "state"   # the cached rows were mapped for the old config
        with open(os.path.join(d, self.app + "__config.json"), "w") as f:
            json.dump(self.cfg, f)
        titles = [r["title"] for r in self.rows(["tickets"], d)]
        self.assertNotIn("Crash on startup", titles, "rows mapped for the old config are not reused")
        self.assertIn("open", titles)


class Slow(http.server.BaseHTTPRequestHandler):
    """lookup-template's sample answers, each after Slow.delay seconds."""
    delay = 0.0
    answers = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        name = {"search": "geocode", "forecast": "weather"}.get(self.path.split("?")[0].strip("/").split("/")[-1], "extra")
        time.sleep(Slow.delay)
        body = json.dumps(Slow.answers.get(name, {})).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass


# Runs the engine with a smaller TOTAL_BUDGET, so a chain can outlast it in a second instead of fourteen.
RUNNER = """import importlib.util, sys
spec = importlib.util.spec_from_file_location("eng", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.TOTAL_BUDGET = float(sys.argv[2])
m.main([sys.argv[1]] + sys.argv[3:])
"""


class ChainBudget(unittest.TestCase):
    """A lookup chain of three steps (geocode, weather, extra) shares one deadline."""

    def setUp(self):
        self.srv = http.server.ThreadingHTTPServer(("localhost", 0), Slow)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        Slow.answers = dict(fixtures_of("lookup-template"), extra={"note": "ok"})
        self.d = tempfile.mkdtemp()
        scripts = os.path.join(EX, "lookup-template", "scripts")
        for f in os.listdir(scripts):
            if f.endswith((".py", ".json")):
                shutil.copy(os.path.join(scripts, f), os.path.join(self.d, f))
        cfg = cfg_of("lookup-template")
        cfg["api"]["base_url"] = "http://localhost:%d" % self.srv.server_address[1]
        cfg["endpoints"]["geocode"]["path"] = "/v1/search?name={query}"
        cfg["endpoints"]["extra"] = {"path": "/v1/extra?lat={geocode.latitude}", "kind": "object", "data": ""}
        cfg["lookup"]["steps"].append("extra")
        with open(os.path.join(self.d, "lookup-template__config.json"), "w") as f:
            json.dump(cfg, f)
        with open(os.path.join(self.d, "runner.py"), "w") as f:
            f.write(RUNNER)

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        shutil.rmtree(self.d, ignore_errors=True)

    def lookup(self, budget, word):
        e = dict(os.environ)
        e.update({"HOME": self.d, "PYTHONDONTWRITEBYTECODE": "1", "BOLT_APP_FIXTURE": "0"})
        t0 = time.time()
        r = subprocess.run([sys.executable, os.path.join(self.d, "runner.py"), os.path.join(self.d, "lookup-template__engine.py"), str(budget), word, "-", "-"],
                           env=e, capture_output=True, text=True, cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout), time.time() - t0

    def test_the_steps_together_stay_inside_one_budget(self):
        Slow.delay = 0.6   # each step alone fits in 1 s; three in a row do not
        rows, took = self.lookup(1.0, "Paris")
        self.assertEqual([r["title"] for r in rows], ["Open-Meteo did not answer in time (all calls together get 1 s)"])
        self.assertLess(took, 1.0 + 0.6 + 1.0, "the run ends near the budget, not after every step")

    def test_a_chain_inside_the_budget_answers(self):
        Slow.delay = 0.05
        rows, _ = self.lookup(5.0, "Paris")
        self.assertTrue(rows[0]["title"].startswith("New York"), rows[0]["title"])


if __name__ == "__main__":
    unittest.main()
