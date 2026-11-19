# Sample document search for Bolt

Compare two fictional roles in an offline library. In Bolt, open `=sejun-acl-demo`,
choose `reader` and search `roadmap`. The reader sees Product roadmap, its snippet
and Fixture Library / Planning / DOC-101. The reviewer sees a second document.

The launcher passes the sample role and query to a Python bridge. It reads the bundled
fixture from disk and evaluates each allow list before ranking eligible documents.
The roles are freely selectable. Every document and source label is fictional.
