# Editorial tools validation — 1.12

Implemented locally on `codex/editorial-tools`, based on main `5a40b20`.
One contributor level uses existing GitHub write permissions. The management
interface stays in this repo and runs locally; private Hub Markdown views provide
shared browsing. No Pages deployment, new external service, publication, or
credential setup occurred.

## Delivery evidence

| Epic #29 child | Implementation and verification |
| --- | --- |
| #39 Attention inbox | Bounded current-blog/local/Hub findings, stale checks/assets, unsynced work and coverage. Explicit selected-Doc Google reads use native feedback or Drive comment fallback; unavailable reads preserve local findings. Viewing never applies/replies/resolves. |
| #40 Publication package | Selected channel drafts, lengths/limits, missing URL, working Doc and retained final-copy snapshot. Manuscript/source hashes and file readback determine freshness. Semantic factual review and requested file exports reuse existing focused guidance. Nothing is sent. |
| #41 Visual companion | Portable Mermaid/Markdown/table/screenshot plan, placement, caption, alt text and illustrative labels, exact manuscript grounding, provenance and staleness. Rendering is conditional on actual available capabilities; a text plan is not a completed image. |
| #42 Claim evidence | Exact manuscript spans and pinned reference quotations, named/origin/hash evidence, supported/contradicted/insufficient/not-checked states, stale coverage. Inspiration cannot serve as factual evidence. |
| #43 Editorial board | Explicit owner/due/stage, author distinction, ready decisions bound to draft, filters/pages, cached Google links, private generated board and next actions. Conflicts/manual generated edits block unsafe replacement. |
| #44 Historical library | Generic collection setup, scoped discovery previews, checkpointed batches, identity/hash-based revisions, original retention, pending extraction, retirement, local catalog/passages, collection pages, candidate lessons and deliberate rule promotion. Two independent synthetic teams remain isolated; a second member rebuilds the catalog from Git. |

The desk's browser checks covered desktop layout, a 390px mobile breakpoint,
saved owner changes, reference excerpt/curation, and shared memory. No browser
errors were reported. The screenshot in the user guide contains sample content.
HTTP fixture checks reject wrong Host/Origin/token, unknown paths, oversized or
wrong-type bodies, and escaping uploads. Source-file containment rejects symlinks
outside the workspace. Scoped fetch fixtures reject private/link-local addresses
and out-of-scope redirects and verify the socket uses the validated public IP.

## Final CI

Disposable Tart clone: `blog-studio-editorial-ci-20261003a`.
macOS 27.0, Python 3.13.15, Git 2.54.0. The signed-in author VM was untouched.

- **253 tests passed** (148.513 seconds), including 18 focused editorial/library/
  management cases and the existing full relevant suite.
- Guidance inventory, both skill package validators, shell syntax and newcomer
  prompt checks passed.
- Real installer install/check/uninstall paths passed for Codex, Claude Code and
  both, including spaces in paths and the GUI/minimal-PATH shell launchers.
- The runtime/package version is **1.12.0**. This fixture guest has no signed-in
  Codex/Claude or Google accounts; installation evidence is not live login evidence.
- After the full CI pass, an import retry gap was fixed: an unchanged locally
  retained post is now requeued when its earlier sharing attempt failed. All
  **19 affected editorial/library/management tests** passed on host Python 3.12,
  including the new recovery regression. **21 final installer tests** also passed.
  Unchanged suite evidence was reused.
- Final documentation/discovery descriptions and screenshot packaging were checked
  separately, together with both skill frontmatter validators and JavaScript syntax.

Local results: `/private/tmp/blog-studio-editorial-ci-results/`.

## Measured library behavior

[Measurement record](estimates/editorial-library-measurement.json): 125 short
synthetic posts, five 25-post batches, 0.202 seconds import, 0.022 seconds initial
index, 0.017 seconds cached query, 390,200 retained source bytes and a 270,336-byte
index. A three-result catalog response was 1,941 characters. These are local
fixture observations, not live-site or large-corpus performance guarantees.

## Live limits and remaining acceptance

Actual Google-native feedback parity remains in #15. Live Codex/Claude and
multiple-member acceptance remain #9/#10. #44 still needs the bounded collection
chosen by a participating team; no real crawl was started during implementation.
The existing issues remain open for review and live evidence.

PDFs remain pending host extraction. DOCX text extraction preserves original
files but does not reproduce page layout in Markdown. Archive links need preview
curation; nested sitemap indexes need separately scoped post sitemaps. Imports
report scope limits and incomplete/failed/pending material and never silently
remove historical snapshots. Candidate lessons do not establish audience
performance or automatically alter team style. Shared-only/older source revisions
are retained for article pins; ongoing articles do not silently adopt updates.

Ordinary GitHub Pages is public even for private source repositories. This
release uses private repository views, not Pages. Git history retains previous
team content; interface retirement is not erasure from Git history.
