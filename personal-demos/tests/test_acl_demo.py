import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "sejun-acl-demo" / "scripts"
SPEC = importlib.util.spec_from_file_location(
    "acl_demo", SCRIPTS / "sejun-acl-demo__app.py"
)
search = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(search)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.documents = json.loads(
            (SCRIPTS / "sejun-acl-demo__fixtures.json").read_text(encoding="utf-8")
        )

    def test_denied_and_unknown_docs_never_reach_ranker_even_with_limit_one(self):
        with patch.object(search, "score_document", wraps=search.score_document) as score:
            rows = search.search_documents(self.documents, "reader", "roadmap", limit=1)
        self.assertEqual([call.args[0]["id"] for call in score.call_args_list], ["DOC-101"])
        self.assertEqual(rows[0]["id"], "DOC-101")

    def test_roles_see_different_results_with_title_snippet_and_source(self):
        reader = search.search_documents(self.documents, "reader", "roadmap")
        reviewer = search.search_documents(self.documents, "reviewer", "roadmap")
        self.assertEqual([row["id"] for row in reader], ["DOC-101"])
        self.assertEqual([row["id"] for row in reviewer], ["DOC-202", "DOC-101"])
        for row in reviewer:
            document = next(doc for doc in self.documents if doc["id"] == row["id"])
            self.assertEqual(row["title"], document["title"])
            self.assertEqual(row["body"], document["snippet"])
            self.assertEqual(row["source"], document["source"])
            self.assertEqual(row["subtitle"], "Sample · " + document["source"])
        payload = json.dumps(reader)
        for field in ("id", "title", "snippet", "source"):
            self.assertNotIn(self.documents[1][field], payload)
            self.assertNotIn(self.documents[2][field], payload)

    def test_invalid_or_unknown_permission_denies_document(self):
        for value in (None, [], "reader", [True], ["reader", "unrecognized"]):
            with self.subTest(allow_roles=value):
                self.documents[0]["allow_roles"] = value
                self.assertEqual(search.search_documents(self.documents, "reader", "roadmap"), [])

    def test_unknown_role_is_rejected_before_source_read(self):
        with patch.object(search, "load_documents") as load:
            rows = search.execute("administrator", "roadmap", Path("unused"))
        load.assert_not_called()
        self.assertEqual(rows, [{"id": "status", "title": "Unknown sample role"}])

    def test_fresh_read_reflects_revoke_and_grant_with_same_query(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures.json"
            path.write_text(json.dumps(self.documents), encoding="utf-8")
            self.assertEqual(search.execute("reader", "roadmap", path)[0]["id"], "DOC-101")
            self.documents[0]["allow_roles"] = ["reviewer"]
            path.write_text(json.dumps(self.documents), encoding="utf-8")
            self.assertEqual(search.execute("reader", "roadmap", path)[0]["title"], "No matching sample documents")
            self.documents[1]["allow_roles"].append("reader")
            path.write_text(json.dumps(self.documents), encoding="utf-8")
            self.assertEqual(search.execute("reader", "roadmap", path)[0]["id"], "DOC-202")

    def test_source_failure_returns_only_generic_status_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures.json"
            path.write_text(json.dumps(self.documents), encoding="utf-8")
            self.assertEqual(search.execute("reader", "roadmap", path)[0]["id"], "DOC-101")
            for text in ("not json", "{}", "[null]"):
                path.write_text(text, encoding="utf-8")
                self.assertEqual(search.execute("reader", "roadmap", path), [
                    {"id": "status", "title": "Sample search unavailable"}
                ])
            path.unlink()
            self.assertEqual(search.execute("reader", "roadmap", path), [
                {"id": "status", "title": "Sample search unavailable"}
            ])

    def test_invalid_allowed_record_fails_without_partial_results(self):
        documents = copy.deepcopy(self.documents)
        del documents[1]["snippet"]
        with patch.object(search, "load_documents", return_value=documents):
            self.assertEqual(search.execute("reviewer", "roadmap", Path("unused")), [
                {"id": "status", "title": "Sample search unavailable"}
            ])

    def test_cli_emits_filtered_json_rows(self):
        result = subprocess.run(
            [sys.executable, str(search.__file__), "reader", "roadmap"],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual([row["id"] for row in json.loads(result.stdout)], ["DOC-101"])
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
