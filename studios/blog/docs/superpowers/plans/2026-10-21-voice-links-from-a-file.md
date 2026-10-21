# Voice Samples From a File of Links: Implementation Plan (addendum)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When learning a voice, a person can upload (or paste) a text file of links to posts, one per line, and every post becomes that author's voice sample in one go, with posts by someone else left out unless kept.

**Owner's request (2026-10-21):** "when we are adding blogs to create voice we should be able to upload a text file of links like this". Example: `/Users/dbbaskette/Downloads/darin-zook-blog-links.txt`, 21 `https://blogs.vmware.com/tanzu/…` links, one per line, named after the author. The owner then asked for this work to live in the "Blog studio features and import" branch (`claude/blog-studio-features-import-e662c9`), beside `2026-10-21-voices-and-styles.md`.

**Status:** a first implementation exists on branch `claude/voice-from-links-wip` (one commit on main `6fdb241`). Its 14 tests pass, as do `check-management.cjs`, ruff, `command_reference.py --check`, `measure_guidance.py --check`, the guidance budget and the root `test_ui_consistency`. The full Blog suite was not run. This plan says what it contains and what to reconcile with the voices-and-styles plan.

All paths are relative to `studios/blog/`.

## What the branch adds

| File | What it does |
| --- | --- |
| `skills/blog-studio/scripts/voice_links.py` (new) | `parse(text, site=None)`: one link per line; skips blanks and `#` comments, strips list markers and `<>`, upgrades `http://` to https, validates with `blog_library.canonical`, drops repeats, lists unusable lines with reasons; caps at 256 KiB and `MAX_POSTS`. Mixed sites return `status: 'choose-site'` with per-site counts; `site=` picks one. `scope_for(links)`: common host and folder (e.g. `https://blogs.vmware.com/tanzu/`), accepted by `blog_library.in_scope`. `author_from_filename()`: `darin-zook-blog-links.txt` → "Darin Zook". `bylines(content)`: author names from JSON-LD (incl. `@graph`, lists, co-authors), then meta (`author`, `article:author`, parsely, `dc.creator`), then `rel=author`, then byline/author classes. `same_author(a, b)`: ignores case, accents, "By", word order and middle initials. `preview(root, data)`: read-only, no network; which links are already in the library, which are new, and an `expected` fingerprint. `run(root, data, reader, delay)`: imports the new links through the existing library `urls` import in batches of 25 (`analyze=False`), continues an interrupted operation, reuses posts already in the library (checking out Hub-only ones), honours `keep` and `retry`, and classifies each post as a `voice-sample` with the author on the record and its library entry; publishes through the Hub adapter. `command(...)`: the CLI entry. |
| `skills/blog-studio/scripts/blog_library.py` | `save_revision(directory, record)` factored out of `curate`. `import_batch` keeps a saved author when the entry has none (a library refresh used to wipe it; tested). New `library voice-links` subcommand: `--file`, `--author`, `--site`, `--import`, `--keep`, `--retry`. |
| `skills/blog-studio/scripts/management.py` | `voice_links_route` for the desk routes `voice-links-preview` and `voice-links-import` (the import requires `expected`). |
| `skills/blog-studio/assets/management/runner.js` | `sAuthorFromFile`, `sVoiceLinks`, `sVoiceLinksCheck`, `sVoiceLinksPreview`, `sVoiceLinksImport`, `sVoiceLinksWords`, `sVoiceLinksResult`. Flow: file or paste → check sheet with the site scope → site choice when mixed → import loop → per-link results with "Keep as sample" and "Try failed links again" → "Learn <name>'s voice", which pre-ticks up to 10 samples. Buttons in `sVoiceTools` and `sVoiceProfile`. |
| `tests/test_voice_links.py` | 14 tests with a stub fetcher (`Pages`) and an HTML fixture builder; synthetic names and hosts only. Parsing, scope, mixed sites, limits, bylines, name matching, import with keep/retry/re-run, library reuse, batches past 25, refresh keeping the author, desk routes, CLI, Team Hub sharing. |
| `scripts/ci/check-management.cjs` | `voiceLinksJourney()`, wired into `sharedPattern`. |
| Docs | `references/voice-flow.md` (chat and CLI), `references/page-tools.md`, `docs/capabilities.md`, regenerated `docs/commands.md`. |

## Reconcile with `2026-10-21-voices-and-styles.md`

That plan's Task 5 brings links in as `{url}` entries through the desk `upload` route, checked by a new `sample_intake.py`, one `author` per request, at most 20 per request. This branch instead uses the library's existing `urls` import (fetch, extraction, scope checks, Hub publishing, batches of 25). Pick one route for links so there are not two fetchers:

- [ ] **Step 1: Decide the route.** Recommended: keep the library import for links (it already fetches, scopes, dedupes against the library and shares through the Hub), and let Task 5's `{url}` upload entry be a thin wrapper that calls `voice_links.run` for a single link, or drop it. Keep Task 5's LinkedIn export work as planned.
- [ ] **Step 2: One sheet on the page.** Task 6's **Voices and styles** sheet gets this branch's link flow as its "Add links to posts" option (file or paste), not a second link sheet. Move the buttons from `sVoiceTools`/`sVoiceProfile` into that sheet.
- [ ] **Step 3: Style samples too.** The same flow can classify posts as `style-sample` for a style; add a purpose choice to the check sheet when Task 1's styles exist.
- [ ] **Step 4: Merge the branch** into `claude/blog-studio-features-import-e662c9` (`git merge claude/voice-from-links-wip` or cherry-pick its one commit), resolve overlaps with Tasks 5 and 6, and run the full Blog check: `python3 scripts/ci/run_tests.py --jobs 6`, `node scripts/ci/check-management.cjs`, `ruff format --check .`, `ruff check .`, both guidance checks; compare failures against a clean `origin/main` export (sandbox port-bind failures exist there).
- [ ] **Step 5: Live check with the owner's file**, only with the owner's go-ahead (it fetches 21 public posts from blogs.vmware.com): import the links for "Darin Zook" in a disposable workspace, confirm 21 rows, bylines matched or flagged, and a voice learned from the samples.
