# One team library: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** finished blogs, blog files, uploads, links and Google Docs land in one shared
library, and a blog picks its facts and examples from it instead of re-adding them.
Spec: `../specs/2026-10-21-team-library-design.md`.

**Precondition:** the styles work (`claude/blog-studio-features-import-e662c9`) is on main:
`styles.py`, the `style` pin on a run, `style-sample` purpose, `style-learn` job.

All paths are relative to `studios/blog/`. Tests first; run each file with
`cd tests && HOME=$TMPDIR/h python3 -m unittest <file>`; `ruff format` and `ruff check .`
before each commit.

## Task 1: Library metadata

Files: `skills/blog-studio/scripts/studio.py`, `blog_library.py`, `hub_workspace.py`,
`tests/test_blog_library.py` (or the nearest).

- [ ] Tests: a source saved with `library.kind`, `library.origin_kind` and
      `library.article` keeps them through `save_revision`, a library refresh and the Hub
      projection; unknown `origin_kind` refused; `kind` must be a known style id.
- [ ] Implement; `source_rows` exposes the fields; `catalog` filters accept `role`, `kind`,
      `author`.
- [ ] Commit: "Give every library item a role, a kind of post and an origin".

## Task 2: Finish lands the blog in the library

Files: `blog_runner.py` (finish), `blog_delete.py`, `tests/test_blog_runner.py`.

- [ ] Tests: Finish creates one source (`reference`+`inspiration`, author, kind from the
      run's style, `written-here`, `article`), content = the published draft text; a
      second Finish updates it (revision 2, same id); delete keeps it and restore keeps the
      link; a team workspace shares it.
- [ ] Implement with the existing save path (`studio.source_command add` / revision).
- [ ] Commit: "Keep every finished blog in the library".

## Task 3: Blog files go to the library by default

Files: `assets/management/runner.js` (`sFilesCard`), `management.py` (`upload_files`),
`scripts/ci/check-management.cjs`, `references/guided-runs.md`.

- [ ] Tests: the files card's keep check is on by default and reads "Keep in the team
      library"; kept items land with role, author and kind; "Just this blog" keeps a file
      as material; journey updated.
- [ ] Commit: "Keep a blog's files in the team library unless told otherwise".

## Task 4: Add to library

Files: `management.py` (new route `library-add-preview` / `library-add`), `voice_links.py`
(reuse `parse`, `scope_for`, bylines), `google_intake.py`, `runner.js` (sheet from the
library screen), `index.html`, `check-management.cjs`, `tests/test_editorial_tools.py`.

- [ ] Tests: files, a list of links (file or pasted) and a Google Doc each preview with
      text size and byline, then save with role, author and kind; refusals: no role, link
      outside scope, oversized, unreadable; idempotent on retry (`expected` fingerprint).
- [ ] Implement; links through `blog_library.import_batch` with `analyze=False`.
- [ ] Commit: "Add files, links and Google Docs to the library in one sheet".

## Task 5: The library screen

Files: `assets/management/app.js`, `index.html`, `management.py` (`catalog` filters, a
`library-selection` action route), `check-management.cjs`.

- [ ] Tests: role, kind and author filters; a selection; the three actions start
      `style-learn`, `voice-learn`, or open New blog from my files with the items ticked as
      examples (`draft.files` seeded from library ids).
- [ ] Commit: "Filter the library and act on a selection".

## Task 6: From the library, and style samples pre-ticked

Files: `runner.js` (`sFilesCard`, a picker sheet, `sWizard`/`sFilesScreen` kind of post
hook), `blog_runner.py` (`create` accepts library ids with per-item roles for this blog),
`check-management.cjs`, `tests/test_blog_runner.py`.

- [ ] Tests: `create` with `library: [{id, role}]` pins each as a source with that role for
      this run only (library record unchanged); the picker lists filtered items and ticks
      them into the files list; choosing a learned style pre-ticks its samples (≤ 8, newest
      first) and a starter style none; untick works; stops line follows.
- [ ] Commit: "Pick facts and examples from the library".

## Task 7: Docs and the full check

- [ ] `references/guided-runs.md`, `references/page-tools.md`, `README.md`,
      `docs/capabilities.md`, `CHANGELOG.md`; `docs/commands.md` if a command changed;
      `measure_guidance.py --check`.
- [ ] Full check: `python3 scripts/ci/run_tests.py --jobs 6`, `node scripts/ci/check-management.cjs`,
      `ruff format --check .`, `ruff check .`; root `test_ui_consistency`. Compare failures
      with a clean `origin/main` export (sandbox port-bind failures exist there).
- [ ] Commit: "Document the team library".
