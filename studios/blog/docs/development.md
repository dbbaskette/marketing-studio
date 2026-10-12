# Developing Blog Studio

The main README is for authors. This page collects repository and maintenance details.

## Layout

- `skills/blog-studio/`: the complete skill: `SKILL.md`, references and the
  Python helpers in `scripts/`. This folder is what gets installed, and
  `VERSION` in it is the only place the version is written.
- `installer/`: `install.py`, the `install.sh` entry point, the Finder launcher
  and the optional Google setup helper.
- `scripts/build.py`: builds the release archives into `build/` (ignored by Git).
- `scripts/ci/check.sh`: the one list of project checks.
- `guidance/manifest.json`: upgrade notice read by 1.x installations; see
  [PACKAGE](../PACKAGE.md).
- `preview/blog-studio.html`: optional local prompt generator for beginners. It
  does not write articles or store content.
- `skills/blog-writing-toolkit/`: the original module collection, kept for
  provenance.

To try the skill from a checkout, open this repository in your AI tool and ask
it to use `skills/blog-studio/SKILL.md`, or install the checkout into a
disposable home:

```sh
sh installer/install.sh install --home /tmp/blog-studio-home --target both --yes
```

To use the optional prompt generator locally:

```sh
python3 -m http.server 8896 --bind 127.0.0.1 --directory preview
```

Visit `http://127.0.0.1:8896/blog-studio.html`.

## Verify

Use Python 3.11 or later. Node is needed for the two browser-script checks.

```sh
bash scripts/ci/check.sh "$(command -v python3)" /tmp/blog-studio-checks
```

That script is what CI and the release workflow run. It checks shell syntax,
validates both skill folders, proves the build is reproducible
(`scripts/build.py --check`), checks the prompt generator and the guidance
inventory, then runs the test suite. Results and the test log are written to
the directory you name. While working, run one test file directly:

```sh
python3 -m unittest discover -s tests -p 'test_installation.py'
```

When guidance text changes, refresh the inventory with
`python3 scripts/measure_guidance.py` before running the checks. Tests use
disposable homes and local Git repositories; they never touch your real skill
folders or accounts. See [verification boundary](local-ci.md) for how the
hosted and self-hosted workflows relate.

## Build and release

```sh
python3 scripts/build.py            # build/*.zip and build/*.zip.sha256
```

To release:

1. Change `skills/blog-studio/VERSION` and add a section headed `## <version>`
   to [CHANGELOG](../CHANGELOG.md).
2. Merge to `main`.
3. `release.yml` sees that tag `v<version>` does not exist, runs the checks,
   builds, and publishes the GitHub Release with the three archives, their
   checksums and that changelog section.

A push that does not change `VERSION` publishes nothing. Raise the major
version when an installed copy can no longer read existing workspaces or Team
Hubs without a migration; otherwise raise the minor or patch number. Team Hub
layout compatibility is tracked separately by the `minimum_runtime` values in
`hub_store.py` and `hub_browse.py`.

## Validation records

[Desk usability validation](desk-usability-validation.md) covers memory/access
handling, responsive layouts and article/finding continuation.

[Desk concurrency validation](desk-concurrency-validation.md) records the
verified request-ordering and source-conflict fixes.

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
