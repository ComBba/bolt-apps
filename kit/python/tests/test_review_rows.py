"""Review fixes: open_url and one bad record must not blank the list."""
import base64
import os
import stat
import sys
import tempfile
import time
import unittest
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bolt_app_kit as k  # noqa: E402


class OpenUrl(unittest.TestCase):
    def test_open_url_takes_only_http_links(self):
        for bad in ("javascript:alert(1)", "file:///etc/passwd", "myapp://x", "//evil.example/x", "https://a.com/ b", "https://a.com/{{x}}"):
            with self.assertRaises(k.KitError):
                k.row("x", open_url=bad)
        self.assertEqual(k.row("x", open_url="https://example.com/a?b=1")["open_url"], "https://example.com/a?b=1")

    def test_open_url_cannot_be_smuggled_as_a_field(self):
        with self.assertRaises(k.KitError):
            k.kv_fields(open_url="javascript:1")


class OneBadRecord(unittest.TestCase):
    def test_safe_row_drops_the_bad_field_and_keeps_the_row(self):
        r = k.safe_row("Item", "sub", url="https://a.com/ has space", open_url="javascript:x", trend=[1, float("nan")], data={"a": 1},
                       tile=k.safe_tile("x", "bad", max=float("inf")))
        self.assertEqual(r["title"], "Item")
        self.assertNotIn("open_url", r)
        self.assertNotIn("url", r)
        self.assertEqual(r["kpi_value"], "")
        self.assertEqual(k.validate_rows([r]), [])

    def test_deep_data_and_infinite_values_do_not_remove_the_row(self):
        deep = cur = {}
        for _ in range(12):
            cur["a"] = {}
            cur = cur["a"]
        r = k.safe_row("Item", data=deep, trend=[float("inf")])
        self.assertEqual(r["title"], "Item")

    def test_trend_over_60_is_sliced_not_refused(self):
        r = k.row("x", trend=list(range(100)))
        self.assertEqual(len(r["trend"]), 60)
        self.assertEqual(r["trend"][-1], 99)



if __name__ == "__main__":
    unittest.main()
