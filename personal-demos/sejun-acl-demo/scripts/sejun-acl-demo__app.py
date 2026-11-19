"""Offline Bolt bridge for two sample roles and one synthetic document library."""

import importlib.util
import json
import sys
from pathlib import Path

ROLES = {"reader", "reviewer"}
DOCUMENT_FIELDS = ("id", "title", "snippet", "source")
FIXTURES = Path(__file__).with_name("sejun-acl-demo__fixtures.json")


def load_documents(path):
    documents = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(documents, list) or any(not isinstance(doc, dict) for doc in documents):
        raise ValueError("Expected a list of sample documents")
    return documents


def allowed(document, role):
    roles = document.get("allow_roles")
    return (
        isinstance(roles, list)
        and all(isinstance(item, str) and item in ROLES for item in roles)
        and role in roles
    )


def score_document(document, terms):
    if any(
        not isinstance(document.get(field), str) or not document[field].strip()
        for field in DOCUMENT_FIELDS
    ):
        raise ValueError("Incomplete sample document")
    title = document["title"].casefold()
    snippet = document["snippet"].casefold()
    scores = [3 * title.count(term) + snippet.count(term) for term in terms]
    return sum(scores) if all(scores) else 0


def search_documents(documents, role, query, limit=5):
    terms = query.casefold().split()
    if role not in ROLES or not terms:
        return []

    # Resolve ACLs before handing any document to the ranker.
    permitted = [document for document in documents if allowed(document, role)]
    scored = [(score_document(document, terms), document) for document in permitted]
    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [
        {
            "id": document["id"],
            "title": document["title"],
            "subtitle": "Sample · " + document["source"],
            "body": document["snippet"],
            "source": document["source"],
        }
        for score, document in scored[:limit]
        if score > 0
    ]


def execute(role, query, path=FIXTURES):
    if role not in ROLES:
        return [{"id": "status", "title": "Unknown sample role"}]
    if not query.strip():
        return [{"id": "status", "title": "Enter a search term"}]
    try:
        rows = search_documents(load_documents(path), role, query)
    except (OSError, ValueError):
        return [{"id": "status", "title": "Sample search unavailable"}]
    return rows or [{"id": "status", "title": "No matching sample documents"}]


if __name__ == "__main__":
    arguments = sys.argv[1:]
    role = arguments[0] if arguments else ""
    query = arguments[1] if len(arguments) > 1 else ""
    fixture_path = Path(arguments[2]) if len(arguments) > 2 else FIXTURES
    kit_path = Path(arguments[3]) if len(arguments) > 3 else FIXTURES.with_name(
        "sejun-acl-demo__bolt_app_kit.py"
    )
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("bolt_app_kit", kit_path)
    kit = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = kit
    spec.loader.exec_module(kit)
    kit.emit(execute(role, query, fixture_path))
