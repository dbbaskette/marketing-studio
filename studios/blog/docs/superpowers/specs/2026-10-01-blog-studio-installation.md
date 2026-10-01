# Blog Studio installation and repository guidance design

Status: Approved and implemented for the initial Mac launcher and portable local engine. The design below records the agreed contract; the completion record in the implementation plan distinguishes automated verification from the remaining live pilot.

Blog Studio should install a small local entry skill and versioned continuity helpers. Detailed writing instructions, modules, templates, rubrics, and pinned upstream references remain maintained in the private `dbbaskette/blog-studio` repository. A new writing task fetches the approved `main` revision, pins that commit, and reads relevant guidance from a local task snapshot. Subsequent turns and resumes use the same pin.

The first installation experience should let a newcomer choose Codex, Claude Code, or both; reuse available tools and GitHub access; explain any missing prerequisite; and finish with a verified starting prompt. Writing continues in the harness. The browser prompt generator remains an optional learning aid.

## Baseline before implementation

- The repository and private GitHub remote exist and are synchronized on `main`.
- `skills/blog-studio/` is a complete portable package with relative local references and four standard-library Python scripts.
- The current ZIP/manual-copy installation copies the detailed guidance as well as the parent. It does not refresh instructions from GitHub or pin a remote revision.
- Source, voice, article, and review persistence helpers are implemented and tested. They do not fetch sources, invoke models, or convert arbitrary document formats.
- ContentForge has a useful local reference for a small entry skill and tested fetch/pin helper. Reuse that design after checking its differences rather than introducing a dependency on the ContentForge repository or tools.

## Proposed user experience

1. Open the trusted installer downloaded from the private repository or a private release. Repository access is required; an anonymous public download link cannot deliver this private package.
2. Choose **Codex**, **Claude Code**, or **Both**. Offer a personal installation by default; keep project-only installation in advanced options.
3. See a short readiness list: chosen harness, repository access, Git, Python, and existing Blog Studio installation. Detect the application as well as its CLI; a missing Codex CLI does not mean the desktop app is missing.
4. Reuse working GitHub access. If it is missing, guide the user through their own sign-in and verify access to this exact private repository.
5. Show the required changes together. Reuse existing dependencies; offer a supported installation method for missing tools. Do not require a package manager just to copy a skill.
6. Install the local entry skill and its versioned helper runtime. Preserve existing unrelated skills and any previous Blog Studio installation for rollback.
7. Run a read-only repository check and a disposable local helper smoke check. Report whether each selected harness can discover the skill; an installed file alone does not establish live discovery.
8. Show **Ready to write**, a copyable starting request, and options for checking setup, updating the local runtime, or repairing installation. Do not create a real article or voice profile during setup.

Initial platform recommendation: **Mac first**, with a portable installation engine and later Windows/Linux launchers. This is provisional pending the user's platform preference. A double-click `Install Blog Studio.command` with short, readable choices is the first launcher; a native signed app is a later packaging option if the launcher is too technical in the newcomer pilot. The terminal must not disappear on failure or claim that a user can bypass operating-system trust checks.

## What goes where

| Location | Content | Update behavior |
|---|---|---|
| Local discoverable skill | Small `SKILL.md`, Codex presentation metadata where applicable, sync entry point, local configuration | Explicit managed install/update |
| Local versioned runtime | Trusted sync, workspace, text-check, and LinkedIn-import helpers | Explicit managed update with verification and rollback |
| Private repository | Main writing guidance, capability map, templates, rubrics, source snapshots, compatibility manifest | Fetch approved `main` when a new task starts |
| Local task snapshot | Guidance and relevant reference files at one commit, task pin, freshness record | Preserve for the active/resumed task |
| Local author workspace | Profiles, originals, evidence, outlines, drafts, reviews, history | Existing local persistence; never part of instruction updates |

Repository guidance is fetched to the computer before reading it. The design does not depend on the harness fetching private Markdown URLs directly. Fetching a repository does not put every file into the model context; file reads remain stage-specific.

Use current documented discovery locations: Codex personal `~/.agents/skills/blog-studio` and project `.agents/skills/blog-studio`; Claude Code personal `~/.claude/skills/blog-studio` and project `.claude/skills/blog-studio`. Both support symlinked skill folders. One managed local package may serve both selected harnesses. Detect existing legacy/custom installations to avoid duplicate names; never silently delete them. Native Windows link behavior needs its own validation before a Windows launcher is released. These are local Codex and Claude Code targets, not a claim of Claude Cowork or cloud installation support. [Codex skill discovery](https://learn.chatgpt.com/docs/build-skills), [Claude Code skill discovery](https://code.claude.com/docs/en/skills).

The installer must not register fourteen modules as fourteen separate top-level skills. They stay progressively loaded under the parent. Keep the original standalone toolkit available as an optional manual package.

## Required tools and optional capabilities

| Tool or capability | Core requirement | Proposed installer behavior |
|---|---|---|
| User's local Codex or Claude Code harness | Yes, at least one selected target | Detect; explain how to install/open it if absent; do not modify provider settings or sign into another AI account |
| Git | Yes for repository guidance | Reuse working Git; offer the supported platform installation route if missing |
| Python | Yes for continuity and sync helpers | Target Python 3.11+ for the new installer/runtime; locate a supported interpreter and record its absolute path |
| GitHub access | Yes while the repo is private | Test actual Git access to the approved repository; account identity is not proof of access |
| GitHub CLI `gh` | Optional convenience | Reuse existing Git auth; offer `gh` if browser sign-in/setup is needed |
| Homebrew | Optional installation method on Mac | Use only if present or explicitly chosen; explain alternatives if absent |
| Word/PDF extraction and export | Optional feature | Prefer available harness tools; report capability support; install a converter only for a chosen document workflow |
| Google tooling | Optional future integration | Keep outside core setup until a concrete Google editing/export workflow is designed |
| Node, model API keys, an MCP server, a hosted app | No core requirement | Do not add them as prerequisites for the current skill/helper workflow |

Python 3.11+ is a proposed support baseline, not a claim that current helpers require that version: the present code uses standard-library features available in Python 3.9+. The new runtime's supported range must be checked in its test matrix.

`gh auth login` supports interactive authentication and `gh auth setup-git` can connect Git's credential helper. Use a user's existing working method first; configure a helper only when necessary and explained. Do not copy tokens into Blog Studio configuration, repository URLs, or logs. [GitHub login](https://cli.github.com/manual/gh_auth_login), [Git credential setup](https://cli.github.com/manual/gh_auth_setup-git).

## Guidance refresh and task continuity

- Approved source: `https://github.com/dbbaskette/blog-studio.git`, branch `main`. Installation must not silently accept another source.
- A new task explicitly fetches that branch and resolves an exact commit. Do not pull, reset, or modify an author's working checkout.
- Stage-specific guidance comes from that commit. Provide a file manifest and read trusted Markdown/reference assets without executing scripts or hooks from the fetched snapshot.
- The manifest declares a guidance schema and required local-runtime capabilities/version. Reject incompatible guidance with an actionable update message rather than guessing new helper commands.
- Run executable continuity helpers from the verified installed runtime. Updating prose guidance is separate from replacing executable code.
- Preserve all relative reference relationships, including the original libraries; validation catches missing paths, unexpected symlinks, invalid text, and oversized files.
- Save the commit/freshness metadata with the task checkpoint. Advancing `main` does not change instructions during an active task or an ordinary resume.
- A new invocation refreshes. If access or network fails, report that current guidance could not be verified. Offer an explicitly labeled prior snapshot if one exists, and wait for the user's choice before using it for a new task. Never silently call cached guidance current.
- An explicit request to refresh an active article can adopt a new pin; keep the old pin and record the switch without deleting article history.

## Update, repair, and removal

An installation record contains managed destinations, runtime version, source commit, selected harnesses, interpreter path, and file fingerprints. Install and update use a staged directory, validation, and atomic activation; failure retains the previous working version. Detect an existing unmanaged skill before replacing it and make the backup concrete.

A readiness/repair operation explains missing tools, duplicate skills, broken links, permission problems, authentication failures, compatibility mismatches, and stale snapshots. Repair operates on managed installation files only.

Uninstall removes selected managed skill links/runtime files and reports any retained versions or caches. It does not delete profiles, article workspaces, drafts, or credentials. Cache cleanup is separate from uninstall because a saved task may still rely on its pinned snapshot. Shared dependencies such as Git/Python/gh remain installed.

## Alternatives and rationale

- **Copy the complete ZIP:** already available and useful offline, but each guidance change needs a replacement installation.
- **Symlink the full live checkout:** simple for a developer, but moving the checkout breaks it and pulling changes can alter instructions mid-task.
- **Small local entry plus pinned repository snapshots:** recommended; supports central guidance maintenance and repeatable tasks with a modest installer/runtime.
- **Plugin distribution:** a potential later delivery adapter. Native plugins can simplify discovery, but do not by themselves promise per-task private Git refresh. Keep the refresh contract explicit and avoid requiring an MCP service to solve installation.

## Acceptance

A new Mac user with private-repository access can choose either supported local harness or both, understand prerequisites, complete setup without copying skill folders by hand, and start an outline-only task. The installed parent loads guidance from a recorded commit. A later task sees a repo guidance change without reinstalling; the original task keeps its pin. Updating a local executable runtime is deliberate and reversible. A failed fetch cannot masquerade as fresh guidance. Existing skills and author work remain intact.

Deterministic installation tests use disposable homes, caches, repositories, and dependency-command fixtures. Live sign-in remains user-controlled. A real clean-machine pilot validates usability, operating-system launch behavior, and discovery separately from those tests.
