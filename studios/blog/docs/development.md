# Developing Blog Studio

The main README is for authors. This page collects repository and maintenance details.

## Source and installation

- `skills/blog-studio/`: the complete skill and its progressive references.
- `bootstrap/blog-studio/`: managed entry point plus verified executable runtime.
- `installer/`: guided launcher, regular shell script, and Python installer.
- `dist/`: installable packages and checksums.
- `preview/blog-studio.html`: optional local prompt generator for beginners. It does not write articles or store content.

Open this repository in your AI tool and ask it to use `skills/blog-studio/SKILL.md`.
An offline installation copies the complete skill folder; see [PACKAGE](../PACKAGE.md).
To use the optional prompt generator locally:

```sh
python3 -m http.server 8896 --bind 127.0.0.1 --directory preview
```

Visit `http://127.0.0.1:8896/blog-studio.html`.

## Verify and package

Use Python 3.11 or later and Node for the optional prompt generator checks.

```sh
python3 -m unittest discover -s tests -v
python3 skills/blog-studio/scripts/validate_package.py
node scripts/ci/check-newcomer.cjs
python3 scripts/measure_guidance.py --check
python3 scripts/package_blog_studio.py
python3 scripts/package_installer.py
```

When guidance changes, run `scripts/measure_guidance.py` without `--check` first.
Build packages after the final source and bundled documentation edits. CI checks
Linux/macOS on Python 3.11 and 3.13. Run `bash scripts/ci/tart-matrix.sh HEAD`
for the same four check cells locally; see [local CI](local-ci.md) for setup,
logs and the remaining automatic-trigger and architecture limitations.
See `scripts/ci/` for isolated Tart validation;
Tart is a developer tool, not an author prerequisite.

[Desk usability validation](desk-usability-validation.md) covers memory/access
handling, responsive layouts and article/finding continuation.

[Desk concurrency validation](desk-concurrency-validation.md) records the
Tart-tested request-ordering and source-conflict fixes.

[Remaining acceptance](remaining-acceptance.md) maps every open issue to delivered
implementation and its live-only remainder. [Google capabilities](google-capabilities.md)
records the team contract and actual connection boundaries.

[Performance workloads and budgets](performance.md) distinguish local synthetic
fixtures from live provider/model latency. Run live acceptance last:
[#9](https://github.com/dbbaskette/blog-studio/issues/9),
[#10](https://github.com/dbbaskette/blog-studio/issues/10), and
[#15](https://github.com/dbbaskette/blog-studio/issues/15).

## Architecture, history, and attribution

[October 4 implementation and issue review](implementation-review-2026-10-04.md)
prioritizes correctness, desk usability, deterministic operations, progressive
loading, and measured performance follow-ups.

- [Progressive disclosure roadmap](progressive-disclosure-roadmap.md) and [guidance inventory](estimates/blog-studio-token-inventory.json).
- [Team Hub](team-hub.md), [Google Docs](google-docs.md), and [Google roadmap](google-docs-roadmap.md).
- [Entry-flow validation](m1-entry-validation.md), [focused guidance](m2-m3-validation.md), and [Google fixtures](g0-g3-validation.md).
- [Usability validation](usability-validation.md) and [privacy review](privacy-review.md).
- [Package notes and licenses](../skills/blog-studio/references/package-notes.md), [source lock](../skills/blog-studio/sources.lock.json), and [BlogForge asset lock](../skills/blog-studio/blogforge.lock.json).
- Original collection: [blog-writing-toolkit](../skills/blog-writing-toolkit/SKILL.md).

The skill repository and private writing Hub remain separate. Diagnostic caches
are disposable local data and must not be imported as team memories.
