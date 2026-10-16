# Verification

`bash scripts/ci/check.sh` checks Python and JavaScript syntax and runs the entire
Marketing Studio unittest suite. Tests cover setup persistence, shared settings,
lossless merges, concurrent writers, outdated forms, validation, native workspace
adapter contracts, process reuse, failed-start cleanup, and HTTP access controls.
HTTP tests need permission to bind disposable loopback ports.

On the configured macOS development machine, `scripts/ci/tart-macos.sh` reuses
`macos-test-suite` and the stopped Golden Gate base. Inspect with `--dry-run`
first. Its guest copies source to disposable storage, records actual environment
versions and logs, and writes PASS only after all checks succeed. The shared
runner stops and deletes its own VM. Do not stop another project's VM to get a
slot. For another machine, call the reusable runner with that machine's path and
an appropriate stopped base.

`python3 scripts/ci/native_acceptance.py` optionally verifies real sibling studio
checkouts. It isolates HOME, Git configuration, shared settings, and each studio's
data folder. It prepares all three native workspaces, independently reads the
saved assistant and workspace, and checks that later defaults cannot move them.
No provider job, real team repository, or real user settings are used.

`python3 scripts/ci/native_launch_acceptance.py` additionally launches all three
native page servers against disposable data. Test-only replacements disable
background update and research actions in the presentation and training runners.
It checks that the native pages serve, repeated Open reuses a process, and closing
the launcher stops every owned process. It requires sibling source checkouts.

Browser acceptance should cover the three-step first run, a reload into the launch
page, settings edits, remote-to-local switching, missing installations, the
computer check, and narrow layouts. Use disposable preferences and synthetic
content only. Signed-in provider and multi-user collaboration tests are outside
this launcher verification; each studio retains its own acceptance requirements.
