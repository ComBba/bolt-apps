"""Cold run 2: a text-only lookup result draws no tile, scoped (@scope/name) queries are percent-encoded into the path, and the
field_sum / field_max stats. Runs on Python 3.9. Nothing here ran inside a real Bolt."""
import http.server
import json
import os
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_cold_run_engine import cfg_of, run, EX  # noqa: E402


class LookupTextOnly(unittest.TestCase):
    def test_lookup_template_widget_is_a_selected_row_preview_with_no_waiver(self):
        cfg = cfg_of("lookup-template")
        w = cfg["lookup"]["widget"]
        self.assertEqual((w["kind"], w["mode"]), ("entity_preview", "selected_row"))
        self.assertIn("tiles_above", w["bind"])
        with open(os.path.join(EX, "lookup-template", "check.json")) as f:
            self.assertNotIn("known_empty_tiles", json.load(f))

    def test_rows_without_a_number_carry_no_tile_fields_and_have_a_body(self):
        r = run("lookup-template", ["New", "York"], env={"BOLT_APP_FIXTURE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = [x for x in json.loads(r.stdout) if x.get("title") != "Sample data"]
        text_only = [x for x in rows if x.get("kpi_value") in (None, "")]
        self.assertTrue(text_only, "the template has text-only rows (Coordinates, forecast link)")
        for x in text_only:
            self.assertFalse([k for k in x if k.startswith("kpi_") and x[k] not in ("", None)], x["title"])
        for x in text_only:
            self.assertTrue(str(x.get("body", "")).strip(), "a text-only row gives the pane a body: " + x["title"])


class Scoped(http.server.BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Scoped.seen.append(self.path)
        body = json.dumps({"name": "@types/node", "version": "9.9.9"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


class ScopedNames(unittest.TestCase):
    def setUp(self):
        Scoped.seen = []
        self.srv = http.server.HTTPServer(("localhost", 0), Scoped)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = "http://localhost:%d" % self.srv.server_address[1]

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_at_and_slash_are_percent_encoded_in_one_path_segment(self):
        cfg = cfg_of("lookup-template")
        cfg["api"].update(base_url=self.base, fixture_default=False, allowed_hosts=[])
        cfg["api"].pop("key_env", None)
        cfg["endpoints"] = {"latest": {"path": "/{query}/latest", "kind": "object", "data": "", "require": ["version"]}}
        cfg["lookup"] = {"steps": ["latest"], "rows": [{"title": "{latest.name} {latest.version}", "body": "ok"}], "widget": cfg["lookup"]["widget"]}
        r = run("lookup-template", ["@types/node"], cfg=cfg, env={"BOLT_APP_FIXTURE": "0"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)[0]["title"], "@types/node 9.9.9")
        self.assertEqual(Scoped.seen, ["/%40types%2Fnode/latest"])


class FieldStats(unittest.TestCase):
    def test_field_sum_and_field_max_with_where(self):
        cfg = cfg_of("portal-template")
        ep = "tickets"
        fx = {ep: [{"id": "a", "n": 3, "s": "x"}, {"id": "b", "n": 9, "s": "y"}, {"id": "c", "n": "4", "s": "x"}, {"id": "d", "s": "x"}]}
        cfg["stats"] = {"total": {"endpoint": ep, "field_sum": "n"}, "biggest": {"endpoint": ep, "field_max": "n"},
                        "x_total": {"endpoint": ep, "where": {"s": ["x"]}, "field_sum": "n"}, "none": {"endpoint": ep, "where": {"s": ["zzz"]}, "field_max": "n"}}
        cfg["overview"] = {"rows": [{"title": "Total {total}", "subtitle": "max {biggest}, x {x_total}, none {none}"}]}
        cfg["app"]["noun"] = "thing"
        with open(os.path.join(EX, "portal-template", "scripts", "portal-template__fixtures.json")) as f:
            fixtures = json.load(f)
        fixtures.update(fx)
        r = run("portal-template", ["overview"], cfg=cfg, fixtures=fixtures, env={"BOLT_APP_FIXTURE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        row = [x for x in json.loads(r.stdout) if str(x["title"]).startswith("Total")]
        self.assertTrue(row, r.stdout)
        self.assertEqual(row[0]["title"], "Total 16")   # 3 + 9 + "4" (a numeric string counts), the row with no n is skipped
        self.assertIn("max 9", row[0]["subtitle"])
        self.assertIn("x 7", row[0]["subtitle"])
        self.assertNotIn("none 0", row[0]["subtitle"])   # a stat with nothing to total is left out, never 0


if __name__ == "__main__":
    unittest.main()
