"""script-template (the Art Institute of Chicago demo): reading the answer, the picture path (thumbnail to inline data: image split over row fields), the host allowlist,
the offline and old-copy states, and that the app file agrees with config.json."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.abspath(os.path.join(HERE, "..", "..", "examples", "script-template"))
sys.path.insert(0, os.path.join(HERE, ".."))
import bolt_app_kit as kit  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60
IMG = "3c27b499-af56-f0d5-93b5-a7f2f1ad5813"


def load():
    spec = importlib.util.spec_from_file_location("script_template_t", os.path.join(EX, "scripts", "script-template__app.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class ScriptTemplateLive(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.home = tempfile.mkdtemp()
        self._h = os.environ.get("HOME")
        os.environ["HOME"] = self.home
        self.cfg = self.m.load_json("config.json")
        self.fx = self.m.load_json("fixtures.json")

    def tearDown(self):
        os.environ["HOME"] = self._h or ""
        shutil.rmtree(self.home, ignore_errors=True)

    def src(self, fixture=True, demos=()):
        return self.m.Source(self.cfg, fixture, list(demos), self.fx if fixture else {})

    def rec(self, **over):
        r = {"id": 1, "title": "A painting", "artist_display": "Someone (French)\nmore", "date_display": "1900", "date_start": 1900, "image_id": IMG, "is_public_domain": True,
             "medium_display": "Oil", "place_of_origin": "France", "department_title": "Dept"}
        r.update(over)
        return r

    def test_only_public_domain_artworks_with_a_picture_and_a_plain_id_are_kept(self):
        raw = {"data": [self.rec(), self.rec(id=2, is_public_domain=False), self.rec(id=3, image_id=None), self.rec(id="../x"), self.rec(id=5, image_id="not/a-uuid"), "junk", self.rec(id=6, title=None)]}
        got = self.m.n_items(raw, self.cfg)
        self.assertEqual([i["id"] for i in got], ["1"])
        self.assertEqual(got[0]["artist"], "Someone (French)")   # first line only
        with self.assertRaises(ValueError):
            self.m.n_items({"data": [self.rec(id="../x")]}, self.cfg)   # records but none usable: unread, not "no artwork"
        with self.assertRaises(ValueError):
            self.m.n_items({"nope": 1}, self.cfg)

    def test_a_year_that_is_not_an_integer_is_left_out_not_zero(self):
        it = self.m.n_item(self.rec(date_start="1900", title="T"), self.cfg)
        self.assertIsNone(it["year"])

    def test_description_html_is_stripped_and_cleaned(self):
        it = self.m.n_item(self.rec(description="<p>One &amp; two</p>\n<p><em>Three</em>‮</p>", credit_line="Gift"), self.cfg)
        self.assertIn("One & two", it["description"]); self.assertIn("Three", it["description"])
        self.assertNotIn("<", it["description"]); self.assertNotIn("‮", it["description"])

    def test_the_picture_is_split_over_fields_under_the_4000_character_cut_and_joins_back(self):
        img = self.m.DATA_PREFIX + "/9j/" + "A" * 9000
        f = self.m.img_fields(img, self.cfg)
        self.assertEqual(sorted(f), ["img1", "img2", "img3"])
        self.assertTrue(all(len(v) <= 4000 for v in f.values()))
        self.assertEqual("".join(f[k] for k in sorted(f)), img)
        self.assertEqual(self.m.img_fields("x" * 16001, self.cfg), {})   # more than the four fields hold: no picture, the row stays
        self.assertEqual(self.m.img_fields("", self.cfg), {})
        row = kit.row("t", "s", **f)   # the kit keeps every field whole
        self.assertEqual("".join(row[k] for k in sorted(f)), img)

    def test_a_thumbnail_too_big_for_the_fields_is_retried_smaller_then_dropped(self):
        s = self.src(fixture=False)
        calls = []

        def fake(cfg, url, accept, cap, timeout):
            calls.append(url)
            return (JPEG, len(calls) == 1)   # the first width is too big
        self.m.http_bytes = fake
        s._thumb_end = 1e12
        out = s.fetch_thumb(IMG)
        self.assertTrue(out and out.startswith("/9j/"))
        self.assertEqual(len(calls), 2)
        self.assertIn("/full/140,/0/", calls[0]); self.assertIn("/full/110,/0/", calls[1])
        calls[:] = []
        self.m.http_bytes = lambda *a: (calls.append(1) or (JPEG, True))
        self.assertIsNone(s.fetch_thumb(IMG))
        self.assertEqual(len(calls), 3)   # every width tried, then no picture
        self.m.http_bytes = lambda *a: (b"<html>blocked</html>", False)   # a 200 that is not a JPEG
        self.assertIsNone(s.fetch_thumb(IMG))

        def boom(*a):
            raise self.m.Fail("fail", "timed out")
        self.m.http_bytes = boom
        self.assertIsNone(s.fetch_thumb(IMG))

    def test_every_host_contacted_is_https_and_in_the_allowlist_and_typed_text_is_only_percent_encoded(self):
        urls = []
        raw = {"data": [self.rec()], "pagination": {"total": 5}}
        m = self.m
        m.http_json = lambda cfg, url, budget: (urls.append(url) or raw)
        m.http_bytes = lambda cfg, url, accept, cap, timeout: (urls.append(url) or (JPEG, False))
        s = self.src(fixture=False)
        (items, total), state = s.search("a&b=c/../d x", True, False)
        s.attach_thumbs(items, network=True)
        self.assertTrue(items and items[0]["img"].startswith(m.DATA_PREFIX))
        self.assertEqual(total, 5)
        self.assertTrue(urls)
        for u in urls:
            p = urllib.parse.urlparse(u)
            self.assertEqual(p.scheme, "https")
            self.assertIn(p.hostname, self.cfg["hosts"])
        q = urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)
        self.assertEqual(q["q"], ["a&b=c/../d x"])   # arrives as one value: nothing typed became a parameter or a path
        self.assertNotIn("&b=c", urls[0])
        self.assertEqual(sorted(set(urllib.parse.urlparse(u).hostname for u in urls)), sorted(self.cfg["hosts"]))   # the API host and the picture host, both named

    def test_the_network_layer_refuses_other_hosts_schemes_and_ports(self):
        load_again = load()
        for url in ("http://api.artic.edu/x", "https://evil.example/x", "https://api.artic.edu:8443/x", "file:///etc/passwd"):
            with self.assertRaises(load_again.Fail):
                load_again.http_bytes(self.cfg, url, "application/json", 100, 2)
        h = load_again._SameHost()
        h.hosts = tuple(self.cfg["hosts"])
        import urllib.request
        req = urllib.request.Request("https://api.artic.edu/a")
        with self.assertRaises(load_again.Fail):
            h.redirect_request(req, None, 302, "Found", {}, "https://evil.example/b")
        with self.assertRaises(load_again.Fail):
            h.redirect_request(req, None, 302, "Found", {}, "https://www.artic.edu/b")   # an allowed host, but not the one that was asked

    def test_a_cached_thumbnail_is_used_without_the_network_and_a_miss_is_not_retried(self):
        s = self.src(fixture=False)
        s.thumbs.put(IMG, {"t": "/9j/AAAA"})
        s.misses.put("00000000-0000-0000-0000-000000000000", {"m": 1})
        self.m.http_bytes = lambda *a: self.fail("the network must not be used")
        items = [{"image_id": IMG}, {"image_id": "00000000-0000-0000-0000-000000000000"}]
        s.attach_thumbs(items, network=True)
        self.assertEqual(items[0]["img"], self.m.DATA_PREFIX + "/9j/AAAA")
        self.assertEqual(items[1]["img"], "")

    def test_a_hostile_cache_file_is_not_a_picture(self):
        s = self.src(fixture=False)
        s.thumbs.put(IMG, {"t": "<script>alert(1)</script>"})
        items = [{"image_id": IMG}]
        s.attach_thumbs(items, network=False)
        self.assertEqual(items[0]["img"], "")

    def test_every_view_passes_the_row_contract_and_a_picture_row_carries_its_picture(self):
        for view, arg in (("overview", ""), ("items", ""), ("pictures", ""), ("grid", ""), ("item", "16568"), ("item", "14598")):
            s = self.src()
            if view == "item":
                it, state = s.detail(arg, False)
                s.attach_thumbs([it], network=False)
                rows = self.m.build(view, arg, it, None, state, self.cfg, True, "")
            else:
                (items, total), state = s.search("monet", False, False)
                s.attach_thumbs(items, network=False)
                rows = self.m.build(view, arg, items, total, state, self.cfg, True, "monet")
            self.assertEqual(kit.validate_rows(rows), [], view)
            pics = [r for r in rows if r.get("img1")]
            self.assertTrue(pics, view if view != "overview" else "the featured artwork has a picture")
            for r in pics:
                joined = "".join(r.get("img%d" % k, "") for k in (1, 2, 3, 4))
                self.assertTrue(joined.startswith("data:image/jpeg;base64,/9j/"))
                self.assertLessEqual(len(joined), 16000)

    def test_a_number_tile_only_on_rows_that_have_a_number(self):
        s = self.src()
        (items, total), state = s.search("monet", False, False)
        rows = self.m.build("overview", "", items, total, state, self.cfg, True, "monet")
        for r in rows:
            if r.get("kpi_label"):
                self.assertIsInstance(r["kpi_value"], (int, float))
        self.assertEqual(sum(1 for r in rows if r.get("kpi_label")), 2)

    def test_offline_shows_one_retry_row_and_an_old_copy_shows_the_data_with_a_label(self):
        s = self.src(demos=("demo-offline",))
        (items, total), state = s.search("monet", False, False)
        self.assertIsNone(items)
        rows = self.m.offline_rows(self.cfg, state, "items")
        self.assertTrue(any(r.get("kpi_badge") == "OFFLINE" for r in rows))
        s2 = self.src(demos=("demo-stale",))
        (items, total), state = s2.search("monet", False, False)
        self.assertTrue(items)
        self.assertIsNotNone(state["stale"])
        self.assertEqual(self.m.banner(state, self.cfg)[0]["kpi_badge"], "OLD COPY")

    def test_the_app_file_is_what_config_json_generates_and_joins_the_picture_fields(self):
        y = self.m.emit_yaml(self.cfg)
        with open(os.path.join(EX, "utilities", "script-template.yaml"), encoding="utf-8") as f:
            self.assertEqual(f.read(), y)
        self.assertIn('image_url: "{{row.img1}}{{row.img2}}{{row.img3}}{{row.img4}}"', y)
        self.assertIn("kind: image_grid", y)
        self.assertNotIn("http", y.split("presentation:")[1].replace("https://", "", 0).split("actions:")[0])   # no web address in any pane bind

    def test_no_key_is_asked_for(self):
        self.assertNotIn("key_env", self.cfg["api"])


if __name__ == "__main__":
    unittest.main()
