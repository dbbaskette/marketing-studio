# Announcements that read like announcements: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** an announcement written from an approved messaging document states the
product's claims in the product's voice, keeps source IDs and editorial notes out of the
reader's text, qualifies once, and can be asked for more depth.
Spec: `../specs/2026-10-21-announcement-writing-design.md`.

All paths are relative to `studios/blog/`. Tests first; run each file with
`cd tests && HOME=$TMPDIR/h python3 -m unittest <file>`; `ruff format` and `ruff check .`
before each commit. Every reference change must pass `scripts/measure_guidance.py --check`.

## Task 1: The messaging role

Files: `skills/blog-studio/scripts/studio.py` (PURPOSES), `management.py` (`upload_files`,
`source-role`, Upload dialog purposes), `assets/management/runner.js` (`sFilesCard` roles,
`LIBRARY_ROLES`), `index.html`, `library_add.py` (role lists), `tests/test_editorial_tools.py`.

- [ ] Tests: an upload with role `messaging` saves purposes `['material', 'messaging']`
      (`['reference', 'messaging']` when kept); `source-role` switches among facts,
      example and messaging; the library catalog's role filter knows `messaging`.
- [ ] Implement; the role select reads "Approved messaging (the product's own claims)".
- [ ] Commit: "Say when an upload is the product's own messaging".

## Task 2: The stance reaches the writer

Files: `blog_runner.py` (`inputs`, `job`), `blog_worker.py` (POLICY),
`references/modules/blog-write.md`, `references/style/software.md`, `tests/test_blog_runner.py`.

- [ ] Tests: a messaging source reaches `payload['sources']` with `stance: 'messaging'`;
      a facts source has `stance: 'evidence'`; existing pins stay byte-identical when no
      messaging source is selected (add the key only when a run has one, as examples do).
- [ ] POLICY paragraph: messaging claims are the announcement's own, stated without
      attribution hedges; limits the document marks are kept; dates and availability
      follow the software-claims guide.
- [ ] `blog-write.md`: "Build from evidence" gains the stance table; `software.md` keeps
      its availability rule and says it applies to dates, versions and entitlements.
- [ ] Commit: "Write approved messaging as the product's own claims".

## Task 3: Notes out of the writing

Files: `blog_runner.py` (`submit`, `document`, `job` guidance), `blog_worker.py` (response
schema), `text_checks.py` (`reader_facing_notes`), `assets/management/runner.js` (`sGate`),
`references/modules/blog-write.md`, `references/modules/blog-repurpose.md`,
`tests/test_blog_runner.py`, `tests/test_blog_studio.py`.

- [ ] Tests: a draft job returns `content` plus `notes: {evidence: [...], gaps: [...]}`;
      the notes are saved beside the stage (`derived/blog-draft-notes.json`) and shown on
      the gate under "Needs you before publishing"; the package's handoff lists the gaps;
      `reader_facing_notes(text)` finds `[source-` and `[Editorial placeholder` and the
      gate's check row fails with the passages.
- [ ] Guidance: the draft and package instructions say where evidence and gaps go, and
      that the writing carries neither.
- [ ] Commit: "Keep source IDs and editorial notes out of the reader's text".

## Task 4: Qualify once, and depth

Files: `blog_runner.py` (`create` accepts `length`; outline and draft guidance),
`references/modules/blog-write.md`, `references/modules/blog-argument-outline.md`,
`references/modules/copy-editing.md` (review finding for repeated qualification),
`assets/management/runner.js` (Length choice on the files screen and wizard step 1),
`scripts/ci/check-management.cjs`, `tests/test_blog_runner.py`.

- [ ] Tests: `length` in `('style', 'short', 'deep')`, refused otherwise, pinned on the
      run, and the draft guidance carries the matching sentence; the review guidance
      names repeated qualification as an editorial finding.
- [ ] Guidance: the capability-section recipe (what, how, what you can now do, one
      example or proof point); the qualify-once rule; the messaging-stance hedge list.
- [ ] Page: Length select beside Kind of post on both screens; journey updated.
- [ ] Commit: "Qualify once, and write to the depth asked for".

## Task 5: A claims map instead of research for supplied material

Files: `blog_runner.py` (`create` pipeline, STAGES, `claims-map` stage), `synthesis_research.py`
or a new `claims_map.py`, `references/modules/blog-deep-research.md` (or a new module),
`assets/management/runner.js` (stops line, stage words), `tests/test_blog_runner.py`.

- [ ] Tests: supplied-only research with only messaging/facts sources builds
      `['claims-map', 'outline', …]`; the claims-map stage lists each claim with its
      source id and passage and never a "not confirmed" finding; web-allowed research is
      unchanged; Balanced does not stop at the claims map.
- [ ] Commit: "Map the claims in supplied material instead of researching them".

## Task 6: Docs and the full check

- [ ] `references/guided-runs.md`, `references/page-tools.md`, `README.md`,
      `docs/capabilities.md`, `CHANGELOG.md`; `docs/commands.md` regenerated;
      `measure_guidance.py --check`; guidance inventory re-recorded if needed.
- [ ] Full check: `python3 scripts/ci/run_tests.py --jobs 6`, `node scripts/ci/check-management.cjs`,
      `ruff format --check .`, `ruff check .`; root `test_ui_consistency`.
- [ ] Commit: "Document approved messaging, notes and depth".
