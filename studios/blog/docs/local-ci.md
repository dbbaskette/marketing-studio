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
and `saypipe-ubuntu-24.04-base` (Ubuntu 24.04 ARM64 kernel, x86 Python through
Rosetta). Override them with
`TART_BASE` and `BLOG_STUDIO_LINUX_BASE`. The base needs Tart Guest Agent,
Git and Node. Ubuntu also needs Python 3, curl, and passwordless guest sudo;
macOS needs Homebrew. Base names identify provisioned local images rather
than immutable images; the actual environment is recorded per run.

Missing Python tooling is provisioned in the disposable clone, never the base:
Homebrew installs uv on macOS; Ubuntu installs python3-venv and uv 0.11.19 in
a scratch virtual environment. uv installs CPython 3.11 and 3.13 in scratch
storage, selecting the available patch releases, like hosted setup-python.
Linux attaches the existing host Rosetta share, registers its x86 ELF handler
per Apple's instructions and installs x86 shared libraries in the disposable
guest. It downloads explicit x86 CPython builds and verifies their ELF format,
`linux-x86_64` platform and `x86_64-linux-gnu` ABI. ARM Python is never used as
evidence for the x86 lane. The Ubuntu mirror setup is for Ubuntu 24.04 only;
do not select an incompatible Linux base without updating its provisioning.
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
| CPU architecture | GitHub runner architecture | Native ARM64 macOS; x86 CPython translated by Rosetta on an ARM64 Linux kernel |
| PR open/synchronize/reopen and main push | Automatic GitHub events | Manually invoked, no persistent queue |
| GitHub status publication | Per-job check runs | Logs and SHA evidence; no automatic status |
| Required merge checks | Depends on repository protection | Does not change or bypass protection |

This implements check-command and Python/OS-family coverage. It does not
establish automatic event/status parity, native x86 kernel/performance parity, or exact
image equality with the moving hosted runners. Keep these limitations explicit
when evaluating replacement of the hosted workflow. The existing
`tart-macos.sh` single-interpreter pilot remains available for historical smoke
runs; it alone is insufficient for full matrix evidence.

Before merging, record the tested SHA and local result paths in the PR. Changes
to a tested revision require a new run. Publication and merge are separate
actions. Do not register a persistent runner or execute incoming PR code on the
host without a separately reviewed trusted controller. The hosted workflow
must stay active until equivalent automatic PR checks are established or
an equivalent safe local integration is established.

## Automatic PR integration pending approval

The requested automatic path is native GitHub Actions delivery to ephemeral
self-hosted runners inside Tart, rather than a custom PR polling queue.
`.github/workflows/verify-tart.yml` is staged on the draft branch and activates
only after an approved merge to the trusted base. The matching
`scripts/ci/verify-tart.workflow.yml` remains a reference template. It preserves the four OS/Python checks, targets only
dedicated self-hosted labels, limits execution to same-repository PRs by
`dbbaskette` and events initiated by that account. Its `pull_request_target`
definition comes from the trusted base so the job filter is evaluated before
queueing and cannot be removed by PR-supplied YAML. It explicitly checks out the
PR head only inside the disposable guest, and uses a read-only repository token with checkout credential
persistence disabled. It has no main-push trigger and no hosted-runner fallback.

Runner registration and persistent VM orchestration are not installed or
approved by staging the workflow. The existing gh login can request
short-lived, repository-scoped registration tokens; no broad GitHub App or new
personal access token is needed. A one-job runner still receives temporary
GitHub runner credentials, so registering it is a separate approved action.

The existing repository is private, has only `dbbaskette` as a collaborator,
and has fork PR workflow execution disabled. Those settings must be rechecked
before runner registration; stop if the access boundary changes. Repository
runner labels alone do not enforce who may submit jobs.

Softnet is installed but cannot start because root privileges are unavailable.
The upstream setuid alternative accepts arbitrary network and privilege-drop
arguments and is a broad root capability; it is not an approved installation
plan. No setuid helper, sudoers edit, security setting, or custom privileged
launcher is created here.

Default Tart NAT keeps the host and LAN reachable from the guest. Owner-only
automation with that existing network configuration was explicitly accepted
by the user for their own PRs. A disposable guest and absence of host credential mounts do not make
NAT a network isolation boundary. No clipboard/audio or host credentials are
shared. Alternatively, a separately approved supported network-isolation
deployment would need verification of host/LAN/IPv6 denial before automation.

Persistent orchestration and short-lived registration-token creation remain
approval steps. Tokens must stay in captured process memory, be sent only over
the local Tart guest control stream, never appear in tool arguments/logs/notes,
and be discarded after registration. Runner credentials live only in a one-job
guest; after its job, deregister and delete that clone. No long-lived GitHub App
private key or new personal access token is required.

A native PR run and its
GitHub check results must pass before disabling only the hosted `ci.yml`.

## Reviewed lifecycle and installation approval

`runner-service.py` is fixed host lifecycle code scoped to
`dbbaskette/blog-studio`; it is not a PR polling scheduler. GitHub delivers jobs
to ephemeral runners. The service boots one Mac and one Ubuntu clone, verifies
the official ARM64 runner 2.337.0 archive SHA-256, and runs the read-only trusted
`runner-bootstrap.sh` before requesting a registration token. Bootstrap installs
the Python pair and Rosetta x86 libraries only inside disposable guests. No PR
checkout, host personal folder, writable host share, or host credential is mounted.
The service checks the approved access policy at startup, before each token
request, and every minute during guest operations; a change stops operation.

Each runner is repository-scoped, `--ephemeral` and `--disableupdate`, with the
dedicated Mac/Linux label. No job executes on the host. After its single job,
the service stops/deletes the clone and removes any remaining exact owned
GitHub runner record. Interrupted cycles are recovered from token-free metadata.
An exclusive local lock prevents duplicate supervisors. Updating the pinned
runner version/digests is deliberate; GitHub may stop accepting an outdated
runner, and the service never falls back to hosted execution.

Safe preparation, without credentials or runner registration:

```sh
/opt/homebrew/bin/python3 scripts/ci/runner-service.py --prepare \
  --state /tmp/blog-studio-native-preflight
```

The existing Mac and Linux bases passed this check, including actual
`Runner.Listener --version` and `config.sh --help`. Eight lifecycle fixtures,
four controller fixtures, ShellCheck and plist/YAML syntax passed. Credential
creation/registration, live native PR delivery, service installation/restart,
and actual GitHub check reporting remain untested pending action-time approval.

The exact installation bundle is:

1. Copy `runner-service.py`, `runner-bootstrap.sh`, and `rosetta-linux.sh` into
   `~/.local/share/blog-studio-ci/`, with a private user-owned directory. Create
   `~/Library/Logs/Blog Studio CI/` privately. Copy the reviewed plist to
   `~/Library/LaunchAgents/com.dbbaskette.blog-studio-tart-runners.plist` and
   start it as the current user's LaunchAgent. No root service, privileged
   helper, sudoers change, new GitHub App, or other repository is involved.
2. Authorize the service's ongoing official authentication flow: existing
   `gh` requests one-hour registration tokens for this repository over GitHub
   HTTPS; captured process memory sends each token via the selected VM's private
   local Tart Unix control socket/stdin into the official runner's supported
   `ACTIONS_RUNNER_INPUT_TOKEN` authentication input. Creation and this local
   exchange are both explicit approval scope. The assistant never enters,
   uploads, prints or copies a token value. Config output is suppressed, secrets
   are masked/removed by the official parser, and registration diagnostics are
   deleted before a PR job. Runner credentials exist only inside the one-job VM.
3. Approve merging draft PR #63 with a `[skip ci]` merge message to activate the
   trusted-base owner-only workflow while suppressing the old hosted push job.
   Open a controlled same-owner validation PR with a `[skip ci]` head commit:
   GitHub skips the old `pull_request` workflow but runs `pull_request_target`.
   Verify all four native checks and cleanup, then carry out the already
   authorized disable of only hosted `ci.yml` and read back its state.

If authentication requires an interactive login or a credential handoff that
the available software flow cannot perform, stop and have the user authenticate
`gh` on their Mac or run the installed service command themselves. Never request
a token in chat. A user-run foreground command, with the LaunchAgent stopped,
is `/opt/homebrew/bin/python3 ~/.local/share/blog-studio-ci/runner-service.py --once`.
Creation consent alone does not authorize a separate assistant credential upload.

Resource bounds: at most two guests/one job per platform, at most four vCPUs
and 4 GiB RAM for Mac plus four vCPUs and 8 GiB RAM for Linux (8 vCPUs/12 GiB
combined). Bases exceeding those limits are refused. Logical disks are the
existing 80/50 GiB APFS-copy-on-write guest disks; physical growth is released
on clone deletion. A job has a 30-minute workflow deadline; the idle/lifecycle
deadline is two hours with at most 35 minutes grace for an already-running job.
Bootstrap is bounded to 30 minutes and guest readiness to four minutes. The two
public runner downloads occupy approximately 270 MiB once in the cache. Duplicate
archives are removed after cleanup; retain at most 30 cleaned run logs per lane
for at most 14 days. GitHub API calls/package downloads consume local resources,
not hosted runner minutes. No paid model calls are part of CI.

Stop the service with:

```sh
launchctl bootout "gui/$(id -u)/com.dbbaskette.blog-studio-tart-runners"
```

SIGTERM stops owned guests and removes their runner records. Inspect private
metadata/logs to confirm cleanup. To uninstall, after stopping and confirming
no unfinished record, remove only that plist, `~/.local/share/blog-studio-ci/`
and `~/Library/Logs/Blog Studio CI/`. Original bases, other VMs, repository
settings and the existing gh login are untouched. Deactivating the new workflow
is a separate GitHub operation; do not substitute all-Actions disablement.

References: [Apple Rosetta guest setup](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms?language=objc),
[Softnet privileges and isolation](https://github.com/openai/softnet#installing).
See also [GitHub skip semantics](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs),
[official runner token-input implementation](https://github.com/actions/runner/blob/v2.337.0/src/Runner.Listener/CommandSettings.cs),
and [Tart local stdin transport](https://github.com/openai/tart/blob/main/Sources/tart/Commands/Exec.swift).

## Automatic delivery acceptance run

The controlled owner PR exercises all four native cells against its exact head
commit before hosted CI is disabled. The installation acceptance check also
stops and restarts the user LaunchAgent and verifies owned runner/VM cleanup.
