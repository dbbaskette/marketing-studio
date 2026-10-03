# Article status card

For “Show status”, “Is everything saved?”, or resume, use the current installed
runtime (1.7+) and saved article, keeping its writing guidance pin unchanged.

```text
... studio.py --root <workspace> select --id <id>
... studio.py --root <workspace> status --id <id> --online --format markdown
```

`--query <title>` resolves a unique match; omitted selectors use the saved active
article or the only blog. Display returned choices if ambiguous. `--details`
adds technical pins and observations only when asked. Omit `--online` offline;
Google then says Not checked, never In sync. An unlinked blog needs no Google login.
For a connector-only session use a fresh native read under the existing Google
status contract; do not install or sign in to another provider merely for a card.

Render the card in chat: title, stage, Google status, local save, Hub status,
check/confirmed-save timestamps, one next step, available Google/GitHub links.
These are ordinary Markdown links, not a web dashboard. Readiness or sign-in
failures do not hide usable local work. A status read never publishes or syncs.

Hub state is the cached local view with historical last-confirmed-save evidence.
For “is everything saved?” or cross-member resume, refresh the selected Hub first
with the existing Hub helper when online, then show the card. If refresh fails,
label the Hub observation unavailable/historical. Queued and pending-review work
has not reached shared main. Do not treat a prior confirmation as a current remote check.
