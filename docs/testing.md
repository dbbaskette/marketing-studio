# Verification

`bash scripts/ci/check.sh` is the suite verification entry point. It runs Python
and JavaScript syntax checks, Marketing Studio's tests, every studio's native
suite and package validator, standalone setup/launch acceptance, a synthetic
Blog Studio Hub journey, and shared-studios acceptance. Blog Studio's pinned
lint tools are installed from its `requirements-dev.txt` in a disposable tools
virtual environment. Logs are retained per outcome.

Tests cover settings merges and locking, stale forms, HTTP access controls,
native workspace contracts, private CLI reuse, deterministic full/subset
archives, source-independent installs, repeat installs, rollback, failed-install
restoration, active-work refusal, and content retention. Shell bootstrap tests
replace package managers and assistants with disposable fixtures; they never
install packages or access an account on the development computer.

On the configured macOS development machine, `scripts/ci/tart-macos.sh` reuses
the shared `macos-test-suite` runner and a stopped base. Inspect with `--dry-run`
first. The guest copies source to disposable storage and records environment
versions and logs. PASS is written only after all checks succeed. The runner
stops and deletes its own clone. Do not stop another project's VM for a slot.

`python3 scripts/ci/native_acceptance.py` verifies the bundled studio checkouts.
It isolates HOME, Git configuration, shared settings, and native data folders.
It prepares all three workspaces and checks that later defaults cannot move
existing work. `native_launch_acceptance.py` runs real native HTTP servers with
test-only replacements disabling background provider and update actions. It
checks page serving, process reuse, and shutdown of owned processes.

All tests use synthetic content and disposable local repositories. No live
assistant job, signed-in provider, private team repository, or real user settings
are needed. Signed-in provider and multi-user acceptance remain separate from
these offline checks.
