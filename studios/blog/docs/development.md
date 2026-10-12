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
- `pyproject.toml` and `requirements-dev.txt`: settings and pinned version for
  ruff, the formatter and linter. Development and CI only; the skill itself
  needs nothing but the Python standard library.
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

That script is what CI and the release workflow run. It lints and checks
formatting, checks shell syntax, validates both skill folders, proves the build
is reproducible (`scripts/build.py --check`), checks the prompt generator and
the guidance budgets, then runs the test suite. Results and the test log are
written to the directory you name. While working, run one test file directly:

```sh
python3 -m unittest discover -s tests -p 'test_installation.py'
```

Tests use disposable homes and local Git repositories; they never touch your
real skill folders or accounts, and the Team Hub tests ignore your own Git
configuration.

The suite takes about five minutes in one process, which is how the workflows
run it. For a faster local run, set `BLOG_STUDIO_TEST_JOBS` to run the same
test files several at a time, each in its own process (about 105 seconds with 8
on an Apple-silicon Mac):

```sh
BLOG_STUDIO_TEST_JOBS=8 bash scripts/ci/check.sh "$(command -v python3)" /tmp/blog-studio-checks
```

The workflows keep the single process because a few tests assert sub-second
timings that a busy shared machine could miss.

The gate for a pull request is the Tart workflow, shown as
`Verify Blog Studio / verify (…)`. The hosted workflow, `Hosted checks`, runs
the same script and is currently disabled in the repository settings. See
[verification boundary](local-ci.md).

### Format and lint

Python in `skills/blog-studio/scripts/`, `installer/`, `scripts/` and `tests/`
is formatted and linted with ruff, at the version pinned in
`requirements-dev.txt`. Other versions format differently, so use that one:

```sh
python3 -m pip install -r requirements-dev.txt   # once
ruff format
ruff check --fix
```

With `uv`, `uvx ruff@<pinned version> format` works without installing
anything. `check.sh` runs both checks first. On a machine with neither ruff nor
`uv` it says that lint was skipped and continues; the pull request gate does
not skip it.

### Guidance budgets

Rewording guidance needs no extra step. The check fails only when the entry, a
route or the whole library grows more than 5% or 50 tokens, whichever is
larger, past the sizes recorded in the
[guidance inventory](estimates/blog-studio-token-inventory.json). Then shorten
the text, or record the new sizes on purpose:

```sh
python3 scripts/measure_guidance.py
```

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
