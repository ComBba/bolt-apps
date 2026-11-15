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

    def test_credential_spellings_stay_redacted_and_benign_names_stay(self):
        for name in ("client_secret", "session_key", "access_key_id", "x_api_token", "refresh_token", "id_token", "X-Amz-Signature", "sig", "credential",
                     "X-Amz-Credential", "sessionToken", "api-key", "APIKEY", "password", "bearer_token"):
            got = k.redact_tree({"u": "https://x/y?a=1&%s=Zq81x7LmP&b=2" % name}, [KEY])["u"]
            self.assertIn("%s=[hidden]" % name, got, name)
            self.assertIn("a=1", got); self.assertIn("b=2", got)
        for name in ("keyword", "monkey", "author", "next_page_token", "page_token", "cursor", "sort_key", "primary_key", "page", "q", "authors", "key_id"):
            url = "https://x/y?%s=abc123" % name
            self.assertEqual(k.redact_tree({"u": url}, [KEY])["u"], url, name)

    def test_credentials_inside_nested_encoded_and_fragment_urls(self):
        cases = ("https://a/x?next=https://h/p?token=Zq81x7LmP&z=1", "https://a/x?redirect=https%3A%2F%2Fh%2Fp%3Ftoken%3DZq81x7LmP%26z%3D1",
                 "https://a/x?return_url=https://h/p%3Fsig%3DZq81x7LmP", "https://a/cb#access_token=Zq81x7LmP&state=1", "https://a/x?next=https://h/p?client_secret=Zq81x7LmP#frag",
                 "https://a/x?u=https%253A%252F%252Fh%253Ftoken%253DZq81x7LmP")
        for c in cases[:5]:
            self.assertNotIn("Zq81x7LmP", k.redact_tree({"u": c}, [KEY])["u"], c)
        self.assertIn("z=1", k.redact_tree({"u": cases[0]}, [KEY])["u"])
        self.assertIn("state=1", k.redact_tree({"u": cases[3]}, [KEY])["u"])
        self.assertIn("next=https://h/p", k.redact_tree({"u": cases[0]}, [KEY])["u"])

    def test_encoded_values_that_contain_equals_signs(self):
        for c in ("https://a/x?next=https%3A%2F%2Fh%2Fp%3Ftoken%3DZq81x7LmP%3D%3D%26z%3D1", "https://a/x?r=https%3A%2F%2Fh%2Fp%3Ftoken%3DabcDEF%3D%3D",
                  "https://a/x?r=https%3A%2F%2Fh%2Fp%3Fsig%3DZq81x7LmP%3Dtail%3Dmore", "https://a/x?r=h%3Ftoken%3Dabc%3D%3D%26ok%3D1"):
            got = k.redact_tree({"u": c}, [KEY])["u"]
            for secret in ("Zq81x7LmP", "abcDEF", "abc%3D", "tail", "more"):
                self.assertNotIn(secret, got, c)
        self.assertIn("%26z%3D1", k.redact_tree({"u": "https://a/x?next=https%3A%2F%2Fh%2Fp%3Ftoken%3DZq81x7LmP%3D%3D%26z%3D1"}, [KEY])["u"])
        self.assertIn("ok%3D1", k.redact_tree({"u": "https://a/x?r=h%3Ftoken%3Dabc%3D%3D%26ok%3D1"}, [KEY])["u"])
        for benign in ("https://a/x?r=h%3Fkeyword%3Dfoo%3D%3D%26author%3Dbob", ):
            self.assertEqual(k.redact_tree({"u": benign}, [KEY])["u"], benign)
        self.assertNotIn("Zq81x7LmP", k.redact_tree({"u": "https://a/x?token=Zq81x7LmP=="}, [KEY])["u"])

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
