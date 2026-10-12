# Verification boundary

Blog Studio owns its checks; shared CI infrastructure owns the machines that
run them.

## The checks

`scripts/ci/check.sh` is the single list. Run it with a supported interpreter
and a fresh results directory:

```sh
bash scripts/ci/check.sh /path/to/python3 /path/to/results
```

It runs the cheap checks first (lint and format, shell syntax, skill validation,
a reproducible build, the prompt-generator check, the guidance budgets) and the
test suite last, printing the end of the test log if a test fails. It needs
Python 3.11+, Git and Node, and no accounts.

The tests run in one process. `BLOG_STUDIO_TEST_JOBS=N` runs the same test
files N at a time for a faster local run; the workflows do not set it. See
[developing](development.md#verify).

### Lint and format

Ruff lints and formats the Python in `skills/blog-studio/scripts/`,
`installer/`, `scripts/` and `tests/`. It is a development tool: its settings
are in `pyproject.toml`, its version is pinned in `requirements-dev.txt`, and it
is never installed with the skill.

`check.sh` runs `ruff check` and `ruff format --check` with exactly the pinned
version. It uses a `ruff` on `PATH` if that is the pinned version; otherwise it
asks `uv` to fetch that version, when `uv` is installed. This is the only step
that can use the network. With neither, it prints
`SKIPPED lint and format check`, records the same line in `lint.txt` and carries
on with the other checks.

Set `BLOG_STUDIO_REQUIRE_LINT=1` to make a missing linter a failure instead of a
skip. All three workflows set it.

### Guidance budgets

`scripts/measure_guidance.py --check` measures the guidance again and compares
the entry, each route and the whole library with the estimates recorded in
`docs/estimates/blog-studio-token-inventory.json`. Each may be up to 5% or 50
tokens larger than recorded, whichever is more, so rewording does not fail the
check. Growth past that margin fails and names the estimates. Shorten the text,
or record the new sizes on purpose with `python3 scripts/measure_guidance.py`.

## Where they run

| Workflow file | Checks appear as | When | Runs on |
| --- | --- | --- | --- |
| `verify-tart.yml` | `Verify Blog Studio / verify (…)` | Pull requests opened by the repository owner from this repository | Self-hosted Tart virtual machines, macOS and Linux, Python 3.11 and 3.13 |
| `ci.yml` | `Hosted checks / hosted (…)` | Every pull request and push to `main`, while the workflow is enabled | GitHub-hosted Linux and macOS, Python 3.11 and 3.13 |
| `release.yml` | `Release / release` | Push to `main`, or run by hand | GitHub-hosted Linux. If the version in `VERSION` has no tag: `check.sh`, build, publish the release |

All three run `check.sh` and nothing else for the project checks.

## The gate

**The Tart workflow is the gate for a pull request.** Merge when its four
checks, `Verify Blog Studio / verify (…)` for macOS and Linux on Python 3.11 and
3.13, are green.

The hosted workflow runs the same list on GitHub's machines and is not the
gate. It has been disabled in the repository's Actions settings since
2026-10-04, so today the Tart checks are the only project checks a pull request
shows. To run the hosted matrix again, enable the workflow there or with
`gh workflow enable ci.yml`.

Two limits to know:

- The Tart workflow runs only for the owner's pull requests from this
  repository. A pull request from a fork or another account gets no checks while
  the hosted workflow is disabled; run `check.sh` on it yourself before merging.
- `main` has no branch protection rule, so GitHub does not enforce the gate. If
  a rule is added, require the four `verify (…)` checks.

`verify-tart.yml` uses `pull_request_target`, so its definition always comes
from `main` and a pull request cannot edit the conditions that decide whether
its code may run on the self-hosted machines. A change to that file therefore
takes effect only after it is merged. The checked-out code, including
`check.sh`, comes from the pull request. Its workflow name and runner labels are
kept as the external runner service expects them, which is why the hosted
workflow is the one that was renamed.

The Tart workflow installs no linter of its own. `check.sh` uses the pinned ruff
if the runner has it and otherwise fetches it through `uv`, which that workflow
already uses to install Python.

`scripts/ci/macos-guest.sh` is this project's additional Mac check for an
isolated guest: it runs `check.sh`, builds the archives, then installs, checks
and removes Blog Studio from the built installer ZIP through the real shell
entry points. The shared runner supplies its source and results mounts. The
guest image is not ours to change, so this script does not require the linter:
lint runs there when the image has the pinned ruff or `uv`, and is otherwise
skipped with the notice in `lint.txt`.

Provisioning virtual machines, registering runners, queue monitoring,
credentials, resource limits and cleanup belong to the separate shared CI
infrastructure and its own repository. They are not Blog Studio features or
installation prerequisites. A local pass does not replace the gate.
