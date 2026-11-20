# Bolt 0.1.181 screenshots for SparcleHQ/bolt-apps PRs #54, #56, #59 and #66

Taken on macOS with Bolt 0.1.181, 2026-11-20. Files named `*-main` come from a build of upstream main, files named `*-fixed` from a build with the PR's change. The #59 apps call a loopback test API whose `tickets` endpoint answers 500.

#66 is built on #59, so its `*-before` files come from a build of #59's branch and its `*-after` files from #66's branch. Both apps call a loopback test API whose `tickets` answer is over 5 MB and whose `projects` include the ids `東京` and `café`. The key shots use a key file holding a 2-character key.
