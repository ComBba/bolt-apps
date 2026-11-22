# Our working standards for contributing to bolt-apps

**Fork-only document.** This file lives in the ComBba fork on the
`docs/working-standards` branch. It is not part of the upstream project and is
never included in a pull request to SparcleHQ/bolt-apps.

Its purpose is narrow: to hold our own work to the standards the Sparcle
maintainers state in [AGENTS.md](../AGENTS.md) and
[CONTRIBUTING.md](../CONTRIBUTING.md) and apply in their reviews, so that
reviewing one of our pull requests costs them as little time as possible.
Where this document and AGENTS.md differ, AGENTS.md wins.

## The standards

1. **Scope.** Fixes to the toolkit, the kit, the examples and the docs only.
   No new apps under `apps/` while the gallery is closed (AGENTS.md,
   CONTRIBUTING.md).

2. **One fix per pull request.** A pull request does one thing. Unrelated
   fixes are separate pull requests, however small. (Maintainer review,
   PR #59.)

3. **A test that fails without the fix.** Every behaviour fix ships with a
   test that fails on the code before the fix and passes after it. A test
   that passes either way does not count. (Verified by the maintainer on
   PRs #58 and #59.)

4. **Show before and after.** The pull request body states the behaviour
   before the change and after it, what was run (the full test suite, the
   checker), and where it was verified — including a run in Bolt itself
   when the change touches runtime behaviour. (PR #54.)

5. **Engine copies stay identical.** The vendored engine copies in the
   examples are byte-identical by design. An engine change is applied to
   every copy, including examples that were added to main after the change
   was written. Never hard-code the number of copies or of apps in a test;
   compare against the actual set. (Lesson: the chart-types breakage after
   PRs #66 and #67 merged, 2026-11-22.)

6. **Only claim what was verified.** Documentation and pull request text
   state only what the code or an actual run proves. Anything unverified is
   labelled unverified, never smoothed over. (Issue #70.)

7. **Sign off every commit.** `git commit -s` (Developer Certificate of
   Origin), per CONTRIBUTING.md. Keep pull requests rebased on current
   main; when a rebase overlaps another change, keep both changes.

8. **Answer every review comment.** Apply the change, or say why not.
   Optional suggestions are acknowledged even when they are not taken.

9. **Coordinate stacked pull requests.** When our pull requests depend on
   each other, keep a merge-order note (issue #69) so the maintainer can
   merge in order without having to reconstruct the stack.

10. **If our merged change breaks main, the follow-up fix is ours.** Open
    it promptly, explain the cause on the original pull request, and do not
    leave the repair to the maintainers. (Chart-types follow-up,
    PR for `fix/chart-types-engine-copy`.)

## Why these exist

The maintainers review carefully and verify by hand — they re-run tests,
diff engine copies themselves, and check claims against the code. A pull
request that arrives small, tested, signed off and honestly described is
cheap to merge. One that arrives large, stacked or overclaimed is
expensive, and the cost lands on them. These standards keep that cost on
our side, where it belongs.
