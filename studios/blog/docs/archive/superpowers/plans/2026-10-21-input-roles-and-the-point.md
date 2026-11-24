# Input roles and "I know the point": implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** An upload says what it is for (facts or an example of the kind of post), examples
never supply facts, a blog from files can start from a known point instead of three angles,
and the voice is chosen in the flow. Spec: `../specs/2026-10-21-input-roles-and-the-point-design.md`.

All paths are relative to `studios/blog/`. Tests first for every task; run each file with
`cd tests && HOME=$TMPDIR/h python3 -m unittest <file>` (every test file imports
`isolation` first). `ruff format` and `ruff check .` before each commit.

## Task 1: Examples leave the sources (runner)

Files: `skills/blog-studio/scripts/blog_runner.py` (`inputs`, `job`), `blog_worker.py`
(`POLICY`), `synthesis_research.py`, `tests/test_blog_runner.py`.

- [ ] Tests: a run whose selected source has purposes `['material', 'inspiration']` reaches
      the worker payload under `examples` (same keys as a source entry) and not `sources`;
      a from-files run excerpts examples under the same budget and names them in
      `excerpted`; `synthesis_research` captures a `material` source and not an
      `inspiration` one.
- [ ] `inputs()`: split by `'inspiration' in purposes`; `payload['examples']`; excerpt both.
- [ ] `job()`: `examples` stay in the payload at every stage except `package`.
- [ ] `POLICY` paragraph (spec §2.2). Guidance for `outline` and `draft` adds one line when
      examples exist: "documents in examples show the kind of post wanted; take their shape,
      not their facts."
- [ ] `synthesis_research.py:60`: `('reference' in purposes or 'material' in purposes) and
      'inspiration' not in purposes`.
- [ ] Commit: "Keep example posts out of a blog's sources".

## Task 2: The carried-over check

Files: `skills/blog-studio/scripts/text_checks.py`, `blog_runner.py` (`job`, gate `checks`),
`references/review/evidence.md` or the review module, `tests/test_text_checks.py` (or the
existing checks test file).

- [ ] Tests: `carried_over(text, examples, allowed)` finds an eight-word run, a number with
      a unit or percent, a URL and a capitalised two-word name that appear in an example
      and not in `allowed`; ignores anything also in `allowed`; ignores code spans and
      quotations (`mask_protected`); returns findings with `rule: 'from-example'`,
      `kind: 'advisory'`, `target`, `start`, `end`, `example` (the example's name).
- [ ] Implement with the stdlib only; cap work at 60 examples × 200 kB.
- [ ] `job()`: at draft and review, extend `payload['mechanical_checks']['findings']` with
      the carried-over findings against `documents.draft` (or the manuscript), allowed =
      sources' text, brief, research bundle facts, the outline.
- [ ] Gate: `review()` adds a check row "No passage carried over from an example" that
      fails when any `from-example` finding exists, and lists each passage (first 120
      characters) in the row's `detail`; `runner.js` `sGate` shows `detail` lines under the
      check when present.
- [ ] Review guidance: a claim traced to an example and to nothing else is `unsupported`.
- [ ] Commit: "Flag passages a draft carried over from an example".

## Task 3: Roles on upload

Files: `skills/blog-studio/scripts/management.py` (`upload_files`, new `source_role`),
`studio.py` if a helper is needed, `assets/management/index.html` (upload dialog),
`tests/test_editorial_tools.py` or the upload tests.

- [ ] Tests: `upload` with `files: [{filename, content, purpose: 'inspiration'}]` saves
      purposes `['material', 'inspiration']` (`['reference', 'inspiration']` with `keep`);
      an unknown per-entry purpose is refused; `source-role {id, role}` switches a material
      file between `facts` and `example`, refuses a library reference, refuses a file pinned
      by a started run, and is idempotent; the dialog's `inspiration` purpose saves and
      shares like a reference.
- [ ] Implement; keep the all-or-nothing rollback in `upload_files`.
- [ ] Upload dialog: option "Example of the kind of post" (`inspiration`).
- [ ] Commit: "Say what an uploaded file is for".

## Task 4: The point, and Balanced from an outline

Files: `blog_runner.py` (`create`, `dispatch` develop, `choose_angle` guard, the
`review_policy.automatic` call), `core/studio_core/review_policy.py`, `tests/test_blog_runner.py`,
root `tests/test_review_policy.py` (or wherever `automatic` is tested).

- [ ] Tests: `create` with `mode: 'from-files'`, `point: true`, title, goal, audience builds
      `['outline', 'draft', 'review', 'package']` (research stages first when the web is
      allowed), no `angles`, `run['angles'] is False`, material pinned as today; `point`
      without a title, goal or audience is refused; the page `develop` action on such a run
      is refused with "This blog has no angles to choose from."; `automatic(record, 'blog',
      'draft', last='package', first='draft')` is False under Balanced and True when
      `first='outline'`.
- [ ] `create`: accept `point` (bool); required brief fields when set; pipeline as the
      ordinary write path; `run['angles'] = not point` for from-files runs.
- [ ] `review_policy.automatic(..., first='outline')`: blog Balanced holds at `(first, last)`.
      The runner passes `first='outline' if 'outline' in run['pipeline'] else 'draft'`.
- [ ] Commit: "Start a blog from files at the point you know".

## Task 5: The page

Files: `assets/management/runner.js` (`sFilesScreen`, `sWizard`, `sStartTasks`,
`sStartBlog` payload), `scripts/ci/check-management.cjs` (`filesJourney`, a wizard journey).

- [ ] Files screen: "Add these files as" select (Facts / Example of the kind of post) above
      the picker, used for the next upload; a role select on each file row calling
      `source-role`; "How to start" choice (Find three angles / I know the point) with
      title, point, reader fields under the second; "Write as" select (Me when a default
      voice is set, profiles with "provisional" labelled, No particular voice + tone);
      Start button text follows the path; submit sends `point`, `profile`, `tone`, `title`,
      `goal`, `audience`.
- [ ] Wizard: the voice select moves out of the "Voice and brand" disclosure to sit above
      the disclosures on step 2 as "Write as"; the disclosure keeps tone, author and brand.
- [ ] Home card: "New blog from my files" with the new description.
- [ ] `check-management.cjs`: extend `filesJourney` (roles, point path, Write as) and the
      wizard journey (Write as visible without opening a disclosure).
- [ ] Commit: "Choose each file's role, the point and the voice on the page".

## Task 6: Docs and the full check

- [ ] `references/guided-runs.md`, `references/page-tools.md`, `README.md`,
      `docs/capabilities.md`, `CHANGELOG.md`; regenerate `docs/commands.md` if a command
      changed (`scripts/command_reference.py --check`); `measure_guidance.py --check` and
      the guidance budget if any reference changed.
- [ ] Full check: `python3 scripts/ci/run_tests.py --jobs 6`, `node scripts/ci/check-management.cjs`,
      `ruff format --check .`, `ruff check .`; root `python3 -m unittest tests.test_ui_consistency`
      and the core review-policy tests. Compare failures against a clean `origin/main` export
      (sandbox port-bind failures exist there).
- [ ] Commit: "Document input roles and the point".
