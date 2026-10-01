# Blog Studio installation and repository guidance implementation plan

Status: I1–I3 implemented and packaged; I4 automated integration checks delivered, with clean-machine and live-harness pilots still pending. No global skill/dependency installation was performed.

Contract: [Installation and repository guidance design](../specs/2026-10-01-blog-studio-installation.md). The initial platform recommendation is Mac first; the installation engine should remain portable. Codex and Claude Code are local harness targets.

## Delivery sequence

| Slice | Outcome | Dependencies | Estimated development tokens |
|---|---|---|---:|
| I1 Repository guidance bootstrap | Small discoverable parent, read-only fetch, exact task pin, compatible guidance manifest | Existing package and private repo | 10–18k |
| I2 Managed installer engine | One verified local package for selected harnesses, readiness, transactional updates and rollback | I1 contract | 12–22k |
| I3 Newcomer launcher and prerequisites | Guided Mac entry, tool detection/setup options, repository-access help, useful success/failure messages | I2 | 10–18k |
| I4 Integrated harness and clean-machine pilot | Real discovery and first outline; update/resume/failure validation; improved release instructions | I1–I3 | 8–15k |
| **Total** | **Installer and repo guidance delivery** | | **40–73k** |

These are input/output development planning ranges, not runtime costs or token budgets enforced by the harness. They partly overlap the existing roadmap's smaller-entry and harness-pilot work; do not simply add both totals. Guidance distillation and expanded document/Google integrations remain separate follow-up work.

## I1 Repository guidance bootstrap

Outcome: detailed writing guidance remains maintained in Git; new tasks fetch/pin an approved revision and progressively read it.

Proposed files (create during implementation):

- `bootstrap/blog-studio/SKILL.md`, `bootstrap/blog-studio/agents/openai.yaml`.
- `bootstrap/blog-studio/scripts/sync_guidance.py`.
- `guidance/manifest.json`, `guidance/entry.md`, and relocated/adapted capability and support references.
- A versioned local-runtime package/manifest for existing `studio.py`, `text_checks.py`, and `linkedin_import.py`.
- `tests/test_guidance_sync.py`; package builders/validators adapted for both bootstrap and optional full snapshot ZIP.

Preserve immutable upstream bytes/licenses/provenance. Keep one maintained operational guidance source; the full offline ZIP becomes a build output of that source rather than another hand-edited instruction tree. Proposed layout may change if a validated build keeps the current relative paths more reliably.

Sync accepts a task/cache location and supported stage selectors; it returns structured freshness, commit, compatibility, snapshot, and guidance-path information. It reads only the approved source/branch, does not modify a working checkout, and does not execute remote code. Use ContentForge's inspected helper as a reference, checking timeout, failure cleanup, compatibility, path containment, and multi-stage access needs.

Acceptance: new task pins A; advancing main to B gives a new task B while original/resumed task remains A. All referenced guidance comes from its pin. Incompatible runtime, missing files, symlinks, invalid/oversized input, authentication failure, and interrupted fetch produce explicit outcomes. Cached fallback needs an author decision. Metadata records do not expose credentials.

Verification owner: implementer. Disposable local repositories test refresh/pinning and failure conditions. Validate transformed guidance links and unchanged upstream hashes once this slice is coherent. Do not treat a frontmatter check as conversational acceptance.

## I2 Managed installer engine

Outcome: installation, update, inspection, repair, rollback, and removal operate on a verified managed package and selected targets.

Proposed files: `installer/install.py`, `installer/targets.py`, `installer/dependencies.py`, `installer/manifest.json`, `tests/test_installation.py`. Use standard-library Python unless a measured need establishes another dependency.

Default personal destinations follow current host documentation; explicit project destinations are advanced. One owned version directory serves both harnesses through supported discovery links. Respect documented custom settings/locations where applicable, detect legacy/duplicate Blog Studio installs, and refuse to overwrite unrelated skill directories. Record an absolute supported interpreter path so GUI-launched sessions do not depend on an interactive shell's PATH.

Provide human-readable results and structured diagnostics. Verify a staged runtime and source manifest before switching the managed current version. Installation records distinguish owned files/links from user data and dependencies. Rollback keeps both harnesses pointing to one verified version. Uninstall retains author data and shared dependencies.

Acceptance: Codex-only, Claude-only, and both selections work; repeat install is idempotent; an existing unmanaged folder requires a concrete replacement/backup choice; failure during either-target activation restores the prior state. Paths with spaces, missing tools, stale links, permission errors, interpreter incompatibility, and duplicate names have useful diagnostics.

Verification owner: implementer. Test against disposable home/project roots and command fixtures; never use production skill directories in automated tests.

## I3 Newcomer launcher and prerequisites

Outcome: a novice can launch setup and make a few clear choices without entering Git, Python, or skill-copy commands.

Proposed files: `installer/Install Blog Studio.command`, platform-specific dependency metadata/adapters, `docs/installation.md`, `docs/troubleshooting.md`, and launcher/dependency tests.

The launcher checks for a usable Python before handing off to I2. Where a prerequisite is missing, use a trusted vendor/package-manager route appropriate to the platform and show what must be installed. Reuse working tools and auth. Homebrew is a choice, not an assumed bootstrap dependency. The launcher must remain usable when Python and Git are absent; it can direct the user to supported installation pages and resume checks afterward. If this is too burdensome in the newcomer pilot, decide whether to ship a self-contained signed launcher rather than claiming one-click setup already works.

Detect the selected harness application/CLI independently. Use existing Git access where possible; offer GitHub CLI browser sign-in/setup only when needed. Verify exact private-repository access. A private repo needs an authenticated download or explicitly distributed installer bundle; document this before promising a universal install URL.

Optional document capabilities appear as available/unavailable/enable later. Core writing setup should not install Word/PDF/Google dependencies automatically. The final readiness page/message offers a copyable starting prompt and optional prompt generator.

Acceptance: users see selected destinations, required changes, progress, cancellation, and actionable failure explanations. No credentials appear in logs; no provider settings are changed; no shared tools or private workspaces are deleted. The installer does not claim live harness discovery from file placement alone.

Verification owner: implementer for fixtures; the final pilot owner validates actual Mac launch/quarantine/trust behavior, missing-tool recovery, and sign-in handoff on a disposable account/machine.

## I4 Integrated pilot and packaging

Outcome: one documented path from private-repo access through installation to a working harness task.

Files: installer/bootstrap distributions under `dist/`, release/package scripts, `README.md`, `PACKAGE.md`, installation/troubleshooting docs, and a dated validation record. Keep offline/full-package distribution labeled separately from the repo-refresh bootstrap.

Pilot Codex and Claude Code separately: discover the installed parent; ask for outline-only; attach supplied text; choose a tone or saved profile; save and stop. Reopen the task with its original guidance pin. Change remote guidance and demonstrate a fresh task using the new revision. Demonstrate offline/access failure and explicit cached fallback. Verify successful runtime update/rollback and uninstall with preserved article data.

Acceptance: a newcomer can explain the next step from the installer's output, both supported harnesses discover the skill, automatic guidance refresh is shown without reinstalling, and no source package/server model call is claimed when it did not run. Record whether the launcher is sufficiently approachable and whether a native signed app is justified.

Verification owner: one final integration owner. Run the full relevant deterministic suite once for the final changed tree, then conduct the live pilot. Reuse earlier evidence for unchanged helpers. A missing fresh-machine or second-harness run remains an explicit validation gap; tests with fixtures cannot close it.

## Review focus and planning boundaries

Check guidance/runtime compatibility, task pins across resume/update, private repo authentication, known source identity, path/ownership boundaries, duplicate skill discovery, atomic activation of both targets, and preservation of author data. Inspect only installation-created logs for credential exposure; do not scan unrelated user files.

This plan adds no hosted writing UI, subscription bridge, model API service, Google collaboration, installer auto-run on this computer, private repo collaborator invitation, or new paid signing service. Platform scope is still provisional until the user's installer-target preference is known.

## Completion record

- Planning: existing package and helpers inspected; ContentForge bootstrap/sync pattern inspected; current official Codex/Claude discovery and GitHub sign-in/setup documentation checked.
- Implementation: small bootstrap; quiet trusted-main fetch with pinned read-only task snapshots; article guidance/runtime persistence; shared managed installer with integrity checks, backups, repair, rollback, and selective uninstall; Mac launcher; private access/browser sign-in support; portable bundles and documentation.
- Layout refinement: operational guidance stays in `skills/blog-studio/`, preserving tested relative reference paths rather than maintaining a second relocated guidance tree. Installer target/dependency logic remains in one standard-library module. The manifest is generated inside the bootstrap.
- Verification: deterministic tests use disposable homes and Git repositories; extracted-bundle portability and source/hash validators verify distributions. CI covers macOS/Linux and Python 3.11/3.13.
- Outstanding pilot: fresh Mac launch/trust/sign-in, live Codex and Claude Code discovery, and conversational route acceptance. Windows support remains unvalidated.
- Validation evidence is summarized in the README and setup guide; the pending live pilot is not counted as completed.
