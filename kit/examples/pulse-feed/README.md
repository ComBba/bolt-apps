# Pulse feed
**What this shows:** a trending overview (a tile row, then one row per story with a trend icon and an open-link arrow), a topic word that merges two public sources in parallel, a preview pane with SOURCE, AUTHOR, AGE and SCORE plus a markdown body with a safety note, and footer buttons Open post, Copy quote and Narrow.
**Edit these files:** `scripts/config.json` (hosts, limits, cache), `scripts/app.py` (`n_firebase`, `n_algolia`, `story_row`, `emit_yaml`) and `scripts/fixtures.json` (sample answers of both APIs).
**Run these commands** from the repo root (once before the first pack: `node toolkit/bin/bolt-apps.mjs keygen`; a higher `--version` each pack):
```
node toolkit/bin/bolt-apps.mjs lint kit/examples/pulse-feed --personal
node toolkit/bin/bolt-apps.mjs check kit/examples/pulse-feed
node toolkit/bin/bolt-apps.mjs pack kit/examples/pulse-feed --personal --version 1.0.1 --out ../pulse-feed-1.0.1.boltpack
node toolkit/bin/bolt-apps.mjs verify ../pulse-feed-1.0.1.boltpack
```

## Notes
- Sources: the Hacker News Firebase API (`https://hacker-news.firebaseio.com/v0`, the front page ids, then one request per story on a thread pool) and the Algolia search API (`https://hn.algolia.com/api/v1/search?query=`). Both are free and need no key. Sample data is invented (`example.com` links); live data is public posts that nobody moderated for you, which is why every preview says so.
- Without a word the app reads 30 stories. With a word it scans the first 60 front-page stories and runs the search side by side, merges by id and sorts by score. A story found by both shows `BOTH`. If one source fails you get the other one and a PARTIAL row; if both fail, an old copy (up to 24 h) or one retry row.
- Narrow is a per-row footer button (a `utility` action built with `kit.action_chain`) that runs `=pulse` again with the longest plain word of the story's title. The install prompt's permission list is computed from the app file's `actions:` block only (`toolkit/lib/assess.mjs` reads nothing else), so a chain added to a row at run time is not in that list.
- Open post opens the story's own https link, or its Hacker News page when it has none. Copy quote puts the title, author and link in the composer; Bolt never runs it.
- Text from a post (title, author) is decoded from HTML entities and stripped of `<>[]()` and backticks before it is shown, so a post cannot draw a link or markup. Whether the launcher renders those fields as plain text is not verified from the launcher source here: treat that as unverified.
- Time limits: `timeout_seconds` in the app file is 20 (Bolt's default would be 10). Both sources share a 14 s deadline, each read stops at that deadline even if a server sends bytes slowly, and a watchdog at 18 s answers with one "Timed out" row and ends the process. Raise `app.timeout` and `api.deadline_s` together if you copy this.
- Words: `=pulse overview` is the front page and `=pulse refresh` re-reads it, so those words cannot be topics when typed bare. To search for one, type `=pulse topic overview`. The topic must be one plain lowercase word.
- Cache: a partial answer is cached for the fresh period but never replaces the complete old copy. Sample mode keeps its cache in memory, so `check` never touches your cache folder.
- Not verified in real Bolt: the preview pane, the open-link arrow and the Narrow chain were checked against the row contract only.
After editing `config.json` or `emit_yaml`, rebuild the app file: `python3 scripts/app.py --emit-yaml > utilities/pulse-feed.yaml`. The key is not needed; nothing secret is stored.

