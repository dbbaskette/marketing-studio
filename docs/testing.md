# Verification

`bash scripts/ci/check.sh` is the suite verification entry point. It runs Python
and JavaScript syntax checks, Marketing Studio's tests, every studio's native
suite and package validator, standalone setup/launch acceptance, a synthetic
Blog Studio Hub journey, and shared-studios acceptance. Blog Studio's pinned
lint tools are installed from its `requirements-dev.txt` in a disposable tools
virtual environment. Logs are retained per outcome. Acceptance Git fixtures run in local disposable
storage; they are copied to the results mount after commands finish. The shared
mount is used for records, not as an active Git working directory.

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
`shared_setup_acceptance.py` starts with each independent studio in turn, finishes
the common setup over HTTP, verifies the native home and settings, then opens all
three independently without Marketing Studio. Root regression tests exercise
preview conflicts, shared completion, late workspace adoption, and the browser
transition from setup at the native root to its home page.

All tests use synthetic content and disposable local repositories. No live
assistant job, signed-in provider, private team repository, or real user settings
are needed. Signed-in provider and multi-user acceptance remain separate from
these offline checks.

For a setup-only repair after a full native suite run, use
`bash scripts/ci/tart-macos.sh --guest scripts/ci/guest-shared-setup.sh`.
This uses the same disposable runner and also repeats the native acceptance and
synthetic Hub/CLI journeys; it leaves the default full gate unchanged.

## Self-contained release bundles

The [local Presentation Studio packaging guide](local-presentation-bundle.md)
describes the extended Apple Silicon bundle and its regeneration command.
`tests/test_presentation_bundle.py` covers deterministic archives, executable
permissions, checksum failures, preservation of earlier builds, source/output
boundaries, dependency locks and disposable build environments.
`tests/test_bundle_sources.py` checks local configuration, tracked working-file
snapshots, Git refs, omitted private files and source integrity using disposable
Git repositories and identities.

`tests/test_distribution.py` checks runtime archive boundaries, checksums, ordinary
file materialization, platform selection, offline companion installation, refusal of
unrelated skills, and restoration after a failed pointer switch. Bootstrap tests use
fake tools and never provision the host.

Build a platform download before testing it. The acceptance script unpacks it into a
disposable HOME, excludes system Python/Node/npm from its launch path, prohibits package
managers and provider jobs, installs the suite, deletes the unpacked download, opens
all native command help, checks both companion versions, and builds a synthetic PPTX
using the bundled production dependencies. It uses no real project or user settings.

```sh
python3 scripts/build_bundles.py --platform macos-arm64
python3 scripts/ci/bundle_acceptance.py dist/marketing-studio-4.1.0-macos-arm64.zip
bash scripts/ci/tart-macos.sh --guest scripts/ci/guest-bundles.sh --dry-run
bash scripts/ci/tart-macos.sh --guest scripts/ci/guest-bundles.sh
```

The `bundles` guest runs the complete suite and the real platform acceptance check
inside the shared disposable macOS runner. Its logs retain the ZIP SHA-256, platform,
runtime versions and source state. Native checks on other platforms are separate;
a successful macOS ARM64 check does not verify Linux or Intel builds. Cross-platform
archive assembly alone is not sufficient evidence for publication.

## Presentation Studio live previews

`test_build_progress.py` exercises incremental event-log reads before process completion,
partial rendering, reconnects, revision and attempt ownership, cancellation after a
workspace is removed, and fallback for older companions. Engine and page tests keep
progress images behind the existing authenticated picture API and leave approval at
the final build gate. The UI uses the existing responsive slide pager.

For a change isolated to Presentation Studio, run
`bash scripts/ci/tart-macos.sh --guest scripts/ci/guest-presentation-progress.sh`.
This runs the complete Presentation Studio suite and validator, suite/subset package
checks, and the final platform bundle acceptance. Reuse the unchanged Blog Studio and
Training Studio evidence from the full suite run.

## Phone and LAN access

`tests/test_network.py` checks the opt-in LAN bridge against loopback-only disposable
HTTP servers: authorization, origin and Host validation, duplicate/framing headers,
request limits, fixed destinations, shutdown, key rotation, and private-link redaction.
`native_launch_acceptance.py` exercises each real native page and authenticated
listing API through the bridge, refusing unauthenticated reads and reusing child
processes. No real user state or provider jobs are involved. Blog Studio's client
checks also omit the secure-context-only UUID API to exercise LAN-safe operation IDs.
See [local-network access](local-network.md) for the user-facing connection boundary.

## Companion version requirements

`test_companion_versions.py` resolves stable and annotated tags from disposable local
Git repositories. It checks numeric version ordering, exact-pin compatibility, cached
update targets, source checksums, tag movement, package/version mismatch, unsafe links,
failed refresh preservation, explicit consent, skipped resolution, and newer-version
preservation. Native installer and upkeep suites verify the shared bindings and UI
update eligibility. Tests never fetch public repositories or install real skills.

For review-level fixes after the full suite, use
`bash scripts/ci/tart-macos.sh --guest scripts/ci/guest-review-levels.sh`.
This repeats shared policy checks, Blog Studio's actual UI behavior checks,
both affected native suites, and all synthetic launch and Hub/CLI journeys.
Reuse full Marketing Studio and Blog Studio Python evidence only while those
implementations are unchanged.

## Synthesis research integration

`test_research_contract.py` runs against the exact locked release helper, with
synthetic dossiers and independent scripted invocations. Native integration suites
cover research handoff, new versus legacy selection, source hashes, revision
requests, the browser worker path, stable Training Studio citations and controlled
Blog Studio bundle sharing. They never run a provider. `STUDIO_TEST_RESEARCH_RUNTIME`
selects disposable source; the guest prepares it with checksum verification.

After unchanged root suite evidence, `bash scripts/ci/tart-macos.sh --guest
scripts/ci/guest-research.sh` runs contract and companion checks, all three full
studio suites and synthetic setup, launch and Hub/CLI acceptance journeys.

For late Stop/contract fixes after passing root, Blog Studio and Presentation
Studio suites, `--guest scripts/ci/guest-research-finish.sh` repeats the affected
shared and Presentation Studio integration checks, the full Training Studio suite
and all CLI acceptance journeys.
