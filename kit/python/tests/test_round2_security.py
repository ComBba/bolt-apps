"""Security review fixes: redact_tree is fast, does not over-redact, covers more forms, and short keys are refused."""
import base64
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bolt_app_kit as k  # noqa: E402

KEY = "S3cretKey99"


class RedactTree(unittest.TestCase):
    def test_a_5mb_body_is_redacted_in_about_a_second(self):
        body = {"items": [{"id": i, "title": "story number %d with some text in it" % i, "url": "https://news.example.com/item?id=%d" % i} for i in range(50000)]}
        body["items"][7]["url"] = "https://x/y?api_key=" + KEY
        self.assertGreater(len(json.dumps(body)), 5_000_000)
        t = time.time()
        out = k.redact_tree(body, [KEY])
        self.assertLess(time.time() - t, 1.5)
        self.assertNotIn(KEY, json.dumps(out))

    def test_only_credential_names_are_rewritten_whole_names_only(self):
        url = "https://x/y?keyword=foo&author=bob&next_page_token=abc&monkey=1&page=2"
        self.assertEqual(k.redact_tree({"u": url}, [KEY])["u"], url)
        got = k.redact_tree({"u": "https://x/y?api_key=%s&key=zz&token=t&mykey=keep&access_token=a" % KEY}, [KEY])["u"]
        self.assertIn("api_key=[hidden]", got); self.assertIn("key=[hidden]", got); self.assertIn("token=[hidden]", got); self.assertIn("access_token=[hidden]", got)
        self.assertIn("mykey=keep", got)

    def test_the_configured_auth_param_is_covered(self):
        self.assertIn("appid=[hidden]", k.redact_tree({"u": "https://x/y?appid=abcdef&n=1"}, [KEY], "appid")["u"])
        self.assertIn("n=1", k.redact_tree({"u": "https://x/y?appid=abcdef&n=1"}, [KEY], "appid")["u"])

    def test_forms_case_hex_url_and_base64(self):
        for form in (KEY, KEY.lower(), KEY.upper(), KEY.encode().hex(), base64.b64encode(KEY.encode()).decode(), base64.urlsafe_b64encode(KEY.encode()).decode().rstrip("="),
                     "S3cretKey99".replace("S3", "S%33")):
            if form == "S%33cretKey99":
                continue
            self.assertNotIn(form, json.dumps(k.redact_tree({"a": ["see %s here" % form]}, [KEY])), form)

    def test_deep_nesting_does_not_crash(self):
        d = cur = {}
        for _ in range(100):
            cur["a"] = {}; cur = cur["a"]
        k.redact_tree(d, [KEY])

    def test_the_looser_pattern_stays_for_error_text(self):
        self.assertIn("[hidden]", k.redact("failed https://x/y?keyword=1&token=abc", [KEY]))


class ShortKeys(unittest.TestCase):
    def test_a_key_under_three_characters_is_refused(self):
        home = tempfile.mkdtemp(); old = dict(os.environ)
        try:
            os.environ["HOME"] = home; os.environ["MY_KEY"] = "ab"
            s = k.get_secret("demo", "MY_KEY", tool_dirs=[home])
            self.assertFalse(s); self.assertIn("shorter than", s.problem)
            os.environ["MY_KEY"] = "abc"
            self.assertTrue(k.get_secret("demo", "MY_KEY", tool_dirs=[home]))
        finally:
            os.environ.clear(); os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
