# Plan: Team library, voices and layout

Design: [the spec](../specs/2026-10-23-library-voices-and-layout-design.md).

1. **Server: matching and authors.** In `library_add.py`: `matching(root, filters)` pages
   the catalog to every matching item (up to 500) for `GET /api/library-matching`;
   `authors(root)` groups readable library posts by author for `GET /api/library-authors`;
   `create_voices(root, data)` queues one `voice-learn` job per ticked author for
   `POST /api/library-voices` (permission once, existing voice updated, fewer than two
   readable posts refused, idempotent per batch operation). The learn selection takes up to
   500 items; a blog still up to 50. Tests in `tests/test_team_library.py`.
2. **Team library screen.** `index.html`: header actions removed; one filter row with More
   filters; a glass selection bar with Select all on this page and Select all matching;
   Refresh Hub beside Check access. `app.js`: per-view toolbar primary, select-all
   behaviour, the table's columns, cards at phone width. `blog.css`: the layout.
3. **Add to library.** Each post's own author by default; "More ways to add" (import a
   whole blog or site; upload one file to summarize, tag or start a blog); Create voices
   for every author on its result.
4. **Create voices for every author** sheet with per-author progress.
5. **Create a voice / Create a style** guided sheets; the Voices screen.
6. **Other screens**: Home order, Blogs title and primary, Settings order, Refresh Hub in
   Team sharing.
7. **Docs**: layout rules in `docs/design/golden-gate.md`; Blog Studio docs that name moved
   controls; CHANGELOG.
8. **Verification**: `check-management.cjs` journeys (select all, create voices, create a
   voice from each source, moved controls reachable), the Blog suite, ruff, build, command
   and guidance checks, root `test_ui_consistency`; before/after screenshots from a
   disposable Blog Studio.
