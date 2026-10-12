# Verification boundary

Blog Studio owns its checks; shared CI infrastructure owns the machines that
run them.

## The checks

`scripts/ci/check.sh` is the single list. Run it with a supported interpreter
and a fresh results directory:

```sh
bash scripts/ci/check.sh /path/to/python3 /path/to/results
```

It runs the cheap checks first (shell syntax, skill validation, a reproducible
build, the prompt-generator check, the guidance inventory) and the test suite
last, printing the end of the test log if a test fails. It needs Python 3.11+,
Git and Node, and no network or accounts.

## Where they run

| Workflow | When | Runs on | What |
| --- | --- | --- | --- |
| `ci.yml` | Every pull request and push to `main` | GitHub-hosted Linux and macOS, Python 3.11 and 3.13 | `check.sh` |
| `verify-tart.yml` | Pull requests opened by the repository owner from this repository | Self-hosted Tart virtual machines, macOS and Linux, Python 3.11 and 3.13 | `check.sh` from the pull request head |
| `release.yml` | Push to `main`, or run by hand | GitHub-hosted Linux | If the version in `VERSION` has no tag: `check.sh`, build, publish the release |

`verify-tart.yml` uses `pull_request_target`, so its definition always comes
from `main` and a pull request cannot edit the conditions that decide whether
its code may run on the self-hosted machines. Its workflow name and runner
labels are kept as the external runner service expects them.

`scripts/ci/macos-guest.sh` is this project's additional Mac check for an
isolated guest: it runs `check.sh`, builds the archives, then installs, checks
and removes Blog Studio from the built installer ZIP through the real shell
entry points. The shared runner supplies its source and results mounts.

Provisioning virtual machines, registering runners, queue monitoring,
credentials, resource limits and cleanup belong to the separate shared CI
infrastructure and its own repository. They are not Blog Studio features or
installation prerequisites. Local success does not waive the required GitHub
checks.
