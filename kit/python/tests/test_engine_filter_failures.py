"""Shared engine: a filter word that cannot ride in a nav arg (C++, cafe with an accent, #12, a/b) keeps the list; a list whose call
failed says it did not load instead of showing zero rows; a tile whose value did not load carries no badge; the portal template
reads its Started date; the form template saves an empty input as empty text and reads "true" and "false" with the yes filter.
Runs on Python 3.9."""
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
from test_cold_run_engine import cfg_of, fixtures_of, load_engine, run, EX  # noqa: E402

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

    def test_a_failed_list_is_not_shown_as_zero_rows(self):
        Answers.status = {"tickets": 500}
        for args in (["tickets"], ["tickets", "open"]):
            rows = self.rows(args)
            text = json.dumps(rows)
            self.assertNotIn("The API returned no rows", text, args)
            self.assertNotIn("0 tickets", text, args)
            self.assertNotIn("0 of 0", text, args)
            self.assertIn("Some data did not load: tickets", text, args)
            unread = [r for r in rows if r["title"] == "Could not read tickets"]
            self.assertEqual(len(unread), 1, args)
            self.assertEqual(unread[0]["nav"], {"view": "tickets", "arg": "refresh"})
            self.assertEqual(unread[0]["kpi_badge"], "ERROR")

    def test_a_detail_whose_child_list_failed_does_not_say_nothing_linked(self):
        Answers.status = {"tickets": 500}
        rows = self.rows(["projects", "P-1"])
        text = json.dumps(rows)
        self.assertIn("Website refresh", text)
        self.assertNotIn("No tickets in this project", text)
        unread = [r for r in rows if r["title"] == "Could not read tickets"]
        self.assertEqual(len(unread), 1)
        self.assertEqual(unread[0]["nav"], {"view": "projects", "arg": "refresh.P-1"})

    def test_a_tile_whose_value_did_not_load_has_no_badge(self):
        Answers.status = {"tickets": 500}
        rows = dict((r["title"], r) for r in self.rows([]))
        for title in ("Open tickets", "Example Co · Summary"):
            self.assertEqual(rows[title]["kpi_value"], "", title)
            self.assertEqual(rows[title]["kpi_badge"], "", "no CLEAR or BEHIND for a count that did not load: " + title)
        self.assertEqual(rows["Projects · 4"]["kpi_badge"], "MIXED", "a tile that loaded keeps its badge")


class TileBadge(unittest.TestCase):
    """A tile value that did not load skips the rule without `if`; a rule on another field still sets the badge."""
    RULES = [{"if": "status==open", "badge": "OPEN"}, {"if": "priority>=4", "badge": "URGENT"}, {"badge": "CLEAR"}]

    @classmethod
    def setUpClass(cls):
        cls.m = load_engine()

    def test_no_value_and_only_the_fallback_matches_gives_no_badge(self):
        self.assertEqual(self.m.make_tile({"value": "priority", "badge": self.RULES}, {"status": "closed"}, {}), (None, ""))

    def test_no_value_keeps_a_badge_from_another_field(self):
        self.assertEqual(self.m.make_tile({"value": "priority", "badge": self.RULES}, {"status": "open"}, {}), (None, "OPEN"))

    def test_no_value_drops_a_plain_word_badge(self):
        self.assertEqual(self.m.make_tile({"value": "priority", "badge": "NEW"}, {"status": "open"}, {}), (None, ""))

    def test_a_value_still_reaches_the_fallback(self):
        self.assertEqual(self.m.make_tile({"value": "priority", "badge": self.RULES}, {"status": "closed", "priority": 2}, {})[1], "CLEAR")


class PortalStarted(unittest.TestCase):
    def test_the_started_field_reads_the_date(self):
        r = run("portal-template", ["projects", "P-1"], env={"BOLT_APP_FIXTURE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        item = [x for x in json.loads(r.stdout) if x["title"] == "Website refresh"][0]
        self.assertEqual(item["f4"], "2026-01-01")


class YesFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_engine()

    def test_yes_reads_booleans_and_their_text(self):
        s = self.m.shown
        for v, want in ((True, "Yes"), (False, "No"), ("true", "Yes"), ("false", "No"), ("yes", "Yes"), ("no", "No"),
                        ("TRUE", "Yes"), (" False ", "No"), ("maybe", "maybe"), (None, "unknown"), ("", "unknown")):
            self.assertEqual(s(v, "yes"), want, repr(v))


class FormRecord(unittest.TestCase):
    def test_an_empty_input_is_saved_as_empty_text_and_the_toggle_as_yes(self):
        home = tempfile.mkdtemp()
        try:
            r = run("form-template", ["5", "Office", "2026-02-01", "", ""], env={"BOLT_APP_FIXTURE": "1", "HOME": home})
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(home, ".bolt-apps", "form-template", "entries.jsonl")) as f:
                saved = [json.loads(x) for x in f if x.strip()]
            self.assertEqual(saved, [{"date": "2026-02-01", "amount": "5.00", "category": "Office", "description": "", "billable": "Yes"}])
        finally:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
