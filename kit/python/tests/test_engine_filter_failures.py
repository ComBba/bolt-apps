"""Shared engine: a filter word that cannot ride in a nav arg (C++, cafe with an accent, #12, a/b) keeps the list and its
notice, cache and retry rows. Runs on Python 3.9."""
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

WORDS = ("C++", "café", "#12", "a/b")


class Answers(http.server.BaseHTTPRequestHandler):
    """Answers by the last path segment: Answers.status[name] is an HTTP status (default 200 with the portal template's sample answer)."""
    status = {}
    payload = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        name = self.path.split("?")[0].strip("/").split("/")[-1]
        code = Answers.status.get(name, 200)
        body = json.dumps(Answers.payload.get(name, {}) if code == 200 else {"message": "server error"}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Live(unittest.TestCase):
    """The portal template against a loopback server, with a key, so the live code paths (partial, stop, cache) run."""

    def setUp(self):
        self.srv = http.server.HTTPServer(("localhost", 0), Answers)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        Answers.status = {}
        Answers.payload = fixtures_of("portal-template")
        self.cfg = cfg_of("portal-template")
        self.cfg["api"].update({"base_url": "http://localhost:%d" % self.srv.server_address[1], "fixture_default": False, "on_missing_key": "setup"})
        self.dirs = []

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def folder(self):
        """A copy of the scripts with the live config; HOME is the same folder, so the cache lives there between runs."""
        d = tempfile.mkdtemp()
        self.dirs.append(d)
        scripts = os.path.join(EX, "portal-template", "scripts")
        for f in os.listdir(scripts):
            shutil.copy(os.path.join(scripts, f), os.path.join(d, f))
        with open(os.path.join(d, "portal-template__config.json"), "w") as f:
            json.dump(self.cfg, f)
        return d

    def rows(self, args, d=None):
        d = d or self.folder()
        e = dict(os.environ)
        e.pop("BOLT_APP_FIXTURE", None)
        e.update({"HOME": d, "PYTHONDONTWRITEBYTECODE": "1", "BOLT_APP_FIXTURE": "0", "EXAMPLE_API_KEY": "abcdef123456"})
        r = subprocess.run([sys.executable, os.path.join(d, "portal-template__engine.py")] + args, env=e, capture_output=True, text=True, cwd=d)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def assert_list_kept(self, rows, word):
        text = json.dumps(rows, ensure_ascii=False)
        self.assertNotIn("not set up correctly", text, word)
        self.assertNotIn("nav must be", text, word)
        self.assertTrue(rows[0].get("nav", {}).get("back"), word)
        for r in rows:
            arg = (r.get("nav") or {}).get("arg") or ""
            self.assertNotIn(word, arg, "the filter word is never put in a nav arg")

    def test_filter_words_keep_the_list_when_a_notice_row_is_drawn(self):
        Answers.status = {"account": 500}   # the tickets view also reads account: a partial notice row with a retry nav
        for word in WORDS:
            rows = self.rows(["tickets", word])
            self.assert_list_kept(rows, word)
            self.assertIn("Some data did not load: account", json.dumps(rows), word)
            self.assertIn('match \\"%s\\"' % word, json.dumps(rows, ensure_ascii=False), word)

    def test_filter_words_keep_the_retry_row_when_every_call_fails(self):
        Answers.status = {"account": 500, "tickets": 500}
        for word in WORDS:
            rows = self.rows(["tickets", word])
            self.assert_list_kept(rows, word)
            self.assertIn("returned an error", rows[-1]["title"], word)
            self.assertEqual(rows[-1]["nav"], {"view": "tickets", "arg": "refresh"}, word)

    def test_filter_word_keeps_the_cache_row(self):
        d = self.folder()
        self.rows(["tickets"], d)   # fills the cache
        time.sleep(2.2)             # the cache row is drawn once the copy is 2 s old
        rows = self.rows(["tickets", "C++"], d)
        self.assert_list_kept(rows, "C++")
        self.assertTrue(any(r.get("kpi_badge") == "CACHED" for r in rows), "the cache row is drawn")

    def test_a_detail_retry_still_keeps_the_item(self):
        Answers.status = {"account": 500}
        rows = self.rows(["projects", "P-1"])
        navs = [r["nav"] for r in rows if (r.get("nav") or {}).get("arg", "").startswith("refresh")]
        self.assertIn({"view": "projects", "arg": "refresh.P-1"}, navs)


if __name__ == "__main__":
    unittest.main()
