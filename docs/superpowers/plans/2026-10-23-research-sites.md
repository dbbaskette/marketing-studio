# Research from your documents, your sites and/or the public web: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** in every studio, research may look in your documents, your sites (a list of base
URLs) and/or the public web; the sites are enforced where pages are captured.

**Spec:** `docs/superpowers/specs/2026-10-23-research-sites-design.md`.

**Architecture:** one core module, `core/studio_core/research_sites.py`, owns the site
format, the choice's shape, old-value mapping, the capture check, the worker guidance and
the words the pages use. Shared settings store the default list under `research.sites`.
Each studio's start form, run record, worker tools and gate use the module.

**Tech stack:** Python 3.11 standard library; plain JavaScript pages with no build step;
`unittest`; each studio's page harness.

## Global constraints

- Standard library only; no frontend build step; full product names.
- UI follows `docs/design/golden-gate.md`: forms and reading surfaces stay opaque.
- Tests use disposable settings (`STUDIOS_CONFIG`), data roots and workspaces; capture
  tests use stub resolvers and openers, never the network; no provider jobs.
- Saved runs written before this change stay readable through `research_sites.legacy()`.

## Task 1: the core module

- [ ] Test first, `tests/test_research_sites.py`: canonical sites (https only, bare
  host/path, no query/fragment/credentials/port, private and loopback hosts, `.`/`..`,
  trailing slash, case), dedup and the 50 limit; `under()` on host and segment boundaries,
  including `blogs.vmware.com.evil.example` and `/tanzu-other/` against `/tanzu`;
  `refused()` with sites only, web only, sites + web; `legacy()` for every old value;
  `source_mode()`, `plan_scope()`, `summary()`, `scope_text()`, `guidance()`.
- [ ] Write `core/studio_core/research_sites.py`.

## Task 2: shared settings

- [ ] Test first in `tests/test_research_sites.py`: `preferences.save` canonicalizes and
  saves `research.sites` through the lock, preserves unrelated values, refuses an invalid
  site with a sentence naming it, and refuses a form that read an outdated list;
  `visible()` carries the list; the Marketing Studio page and a standalone studio's
  onboarding page round-trip it.
- [ ] `studios_config.py`: `research` is a settings group whose `sites` is a list.
- [ ] `preferences.py`: `research` in `check()`, `visible()` and `save()`.
- [ ] `setup_web/index.html`, `app.js`, `home.css`: the Research sites card in Shared
  settings (not first-run setup); `tests/test_ui_consistency.py` style checks still pass.

## Task 3: Blog Studio

- [ ] Tests first: the start screens and files screen send `research_from`; `blog_runner`
  create validates it, pins the list, and maps old `research_policy` values; the writing
  preferences research default takes the new shape; `synthesis_research` passes a
  `research_sites.Scope` to `blog_library.fetch`, so off-site URLs and redirects become
  source limits naming the sites; sites + web allows any public URL; the task scope names
  the sites; page journey (`scripts/ci/check-management.cjs`).
- [ ] Implement in `assets/management/runner.js`, `scripts/blog_runner.py`,
  `scripts/synthesis_research.py`, `scripts/blog_library.py`; docs and CHANGELOG.

## Task 4: Presentation Studio

- [ ] Tests first: `decks.check_form` round-trips `research_from` and maps old
  `research_sources`; `worker_tools.prepare(..., research=)` and `save_source` refuse an
  off-site URL, an off-site redirect, a lookalike host and a path-prefix neighbour, and
  allow any public URL with the web on; `research_steps` names the sites in the task
  scope and guidance and chooses `source_mode`; the desk journey shows the control and the
  summary line.
- [ ] Implement in `skills/presentation-studio/scripts/desk/app.js`, `runner/decks.py`,
  `runner/research_steps.py`, `runner/worker_tools.py`; docs.

## Task 5: Training Studio

- [ ] Tests first: form step 3 round-trips `research_from` and maps old `sources`;
  worker tools refuse off-site captures as above; the engine's research task names the
  sites, chooses `source_mode` and the plan scope; the desk journey; settings.
- [ ] Implement in `skills/training-studio/scripts/desk/app.js`, `runner/engine.py`,
  `runner/worker_tools.py`, `runner/setup.py` / `runner/settings.py`; docs and the
  state-transition matrix row.

## Task 6: verification

- [ ] Root tests and each studio's full suite; compare failures with a clean
  `git archive origin/main` export.
- [ ] Push `claude/research-sites`; open the pull request against main.
