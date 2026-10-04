# Local CI coverage and operation

Run all four compatibility cells on this Mac, without hosted Actions:

```sh
bash scripts/ci/tart-matrix.sh HEAD
```

Use `--dry-run` to inspect the exact SHA, bases, versions and results location.
Use `--platform macos` or `--platform linux` for a focused run. A full matrix is
required before claiming the hosted workflow's platform/version coverage.

The runner archives only the selected committed revision. Uncommitted files,
host Git configuration and account credentials are not shared. The two source
mounts are read-only; builds and tests use a copy inside each disposable guest.
Results default to `/tmp/blog-studio-matrix-runs/`; set
`BLOG_STUDIO_TART_RUNS_DIR` to an absolute directory to retain them elsewhere.
Each run records the full SHA, Tart version, guest OS/tool versions, cell logs,
and a final `PASS` only after all checks and smoke tests succeed. A failing
Python cell does not skip the other version; a failing guest does not skip the
other platform. Guest execution is limited to 30 minutes and readiness to four
minutes. Clones and logs are retained, and the runner stops only its own clones.

## Prepared environments

The default stopped bases are `tanzu-brand-golden-gate-base` (macOS 27 ARM64)
and `saypipe-ubuntu-24.04-base` (Ubuntu 24.04 ARM64). Override them with
`TART_BASE` and `BLOG_STUDIO_LINUX_BASE`. The base needs Tart Guest Agent,
Git and Node. Ubuntu also needs Python 3, curl, and passwordless guest sudo;
macOS needs Homebrew. Base names identify provisioned local images rather
than immutable images; the actual environment is recorded per run.

Missing Python tooling is provisioned in the disposable clone, never the base:
Homebrew installs uv on macOS; Ubuntu installs python3-venv and uv 0.11.19 in
a scratch virtual environment. uv installs CPython 3.11 and 3.13 in scratch
storage, selecting the available patch releases, like hosted setup-python.
Provisioning requires outbound package downloads and local disk/time, but no
GitHub Actions minutes or paid model calls. macOS additionally installs
Homebrew Python 3.13 to exercise the launcher's minimal-PATH discovery.

## Check parity

| Check | Hosted `ci.yml` | Local matrix |
| --- | --- | --- |
| Full unittest discovery | Each OS/Python cell | Each of four cells |
| Installer install/update/rollback/repair and extracted zip/checksum fixtures | In unittest suite | Same suite per cell |
| Newcomer prompt checks | Each cell | Each cell |
| Guidance budget and both source/package validators | Each cell | Each cell |
| Shell and macOS launcher syntax | Each cell | Each cell |
| Real offline Codex/Claude/both install/check/uninstall | Unit fixtures only | Added in both guests |
| GUI-PATH discovery and quarantine assessment | Not explicit | Added in macOS guest; assessment never bypasses protections |
| Operating system/version | `ubuntu-latest`, `macos-latest` | Prepared Ubuntu 24.04 and macOS 27 |
| CPU architecture | GitHub runner architecture | Local ARM64; Linux x86_64 is not covered |
| PR open/synchronize/reopen and main push | Automatic GitHub events | Manually invoked, no persistent queue |
| GitHub status publication | Per-job check runs | Logs and SHA evidence; no automatic status |
| Required merge checks | Depends on repository protection | Does not change or bypass protection |

This implements check-command and Python/OS-family coverage. It does not
establish automatic event/status parity, Linux x86_64 compatibility, or exact
image equality with the moving hosted runners. Keep these limitations explicit
when evaluating replacement of the hosted workflow. The existing
`tart-macos.sh` single-interpreter pilot remains available for historical smoke
runs; it alone is insufficient for full matrix evidence.

Before merging, record the tested SHA and local result paths in the PR. Changes
to a tested revision require a new run. Publication and merge are separate
actions. Do not register a persistent runner or execute incoming PR code on the
host without a separately reviewed trusted controller. The hosted workflow
must stay active until the user accepts the remaining event/platform gaps or
an equivalent safe local integration is established.
