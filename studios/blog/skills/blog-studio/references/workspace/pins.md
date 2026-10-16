# Guidance version of an article

Read only when the author asks which guidance an article used, or asks to move
an article to the installed version. Routine resume uses [resume](resume.md).

Guidance is the installed skill. A new article records that version as
`guidance.revision` automatically; nothing is downloaded or bound by hand. The
record lets reviews be judged against the guidance that produced them, so
installing an update does not change it.

When the author asks to use the current guidance for an existing article:

```text
... article guidance --id <id> --adopt
```

This records the installed version, keeps the earlier value in
`guidance_history`, and makes completed reviews stale because they were judged
under the earlier guidance. Offer to rerun the checks the author still needs.
Without `--adopt` the command only fills in a missing record and refuses to
replace a different one. Never adopt on your own initiative; an update alone
does not select newer sources, voices or team context either.

Articles started before version 2.0, or checked out from a Team Hub, can show a
commit hash as the revision plus `task`, `runtime` or `freshness` fields. They
are history: the article still loads, saves and syncs. Always run helpers from
this skill's `scripts/`, never from a saved `runtime` path. The earlier
instruction snapshot is not restored; work continues with the installed
guidance, and `--adopt` records that when the author asks.
