# Marketing Studio: design spec and implementation plan

> Historical proposal. See [the implemented architecture](architecture.md) for the current Marketing Studio scope.
**Date:** 2026-10-15 · **Status:** draft for review · **Repo:** `marketing-studio` (this folder; not yet a git repository)

This document has two parts.

- **Part 1, the spec**, covers what we are building and why: one repository, a shared core, a home page that does set-up once and opens each studio, and the migration of the three existing repositories.
- **Part 2, the plan**, is the ordered work, in phases. Phases 0–4 are written step by step with code. Phases 5–8 are written to the file and test level. They touch code that other sessions are changing today (see §2.6), so re-check them against the tree when each phase starts.

The design was not settled one question at a time. Where a question would normally have been asked, a decision was taken instead, and §1.3 lists each one so it can be overturned.

---

# Part 1: Design spec

## 1.1 Goal

A person installs **Marketing Studio** once and opens it. On the first visit, one home page:

- asks for everything the studios share,
- checks the computer once,
- and then opens Training Studio, Presentation Studio or Blog Studio, each already set up.

Behind the page, the three studios move into one repository. They share one core of code, one set of companion-skill pins and one installer. Each studio remains its own skill for Claude Code and Codex.

**Separate where the assistant loads skills; shared where code is maintained.**

### Non-goals (this round)

- A single web origin serving all three studios. Each studio keeps its own local server and port; see §1.14.
- Merging the three pipelines, meaning research → outline → build for decks, training stages, and blog stages. Only the machinery underneath them is shared.
- Moving the brand skill (`tanzu-brand`) or the harness skills into this repository. They keep their own repositories and release cycles. This repository pins their versions.
- Windows support. The studios support macOS and Linux today, and that stays.

## 1.2 What exists today

These facts were gathered from the three repositories on 2026-10-15.

| | Training Studio | Presentation Studio | Blog Studio |
|---|---|---|---|
| Server | `runner/studio.py serve`, built on the desk security base | Same; copied from Training | `skills/blog-studio/scripts/start_studio.py open` |
| UI | `skills/training-studio/scripts/desk/` (vanilla JS, `app.js` ~6.4k lines) | `.../desk/` (`app.js` ~5.4k lines) | `skills/blog-studio/assets/management/` |
| Key in the link | `#token=<key>`, header `X-Training-Studio-Token` | `#token=<key>`, header `X-Presentation-Studio-Token` | `#<key>`, header `X-Blog-Studio-Token` |
| Port | 0 (the OS picks one) | 0 | 0 |
| One at a time | `runner.pid`, one per computer | `runner.pid`, one per computer | A lock per workspace |
| Data folder | `~/.local/share/training-studio` | `~/.local/share/presentation-studio` | `~/.local/share/blog-studio`, plus the workspace (default `~/blogs/.blog-studio`) |
| Shared config `~/.config/studios-config.json` | Reads and writes | Reads and writes | On `origin/main` (2.1.0) only; local `main` is behind |
| Companion skills | harness-research 0.8.1, harness-slides 0.14.1 | harness-research 0.8.1, harness-slides 0.14.1 (was 0.8.0 until PRs #5–#6) | None (research guidance is vendored) |
| CI | `ci.yml` runs `scripts/ci/check.sh`; self-hosted Tart verify | None, so the local suite is the only gate | `ci.yml` ("Hosted checks") is **turned off**; the self-hosted Tart verify is the PR gate; release zips are made by `scripts/release.sh` |

Copied code:

- Presentation Studio's `vendor.json` lists **80 files** copied from Training Studio at three revisions. They have drifted. `engine.py` differs by about 4,000 lines and `upkeep.py` by about 1,100.
- Blog Studio copies `style.css`, `markdown.js`, `studio_sync` and `studio_brand` from Training Studio.
- `style.css` (2,301 lines) and `markdown.js` (360 lines) are **byte-identical** in all three studios.
- `computer.py` (the computer check) is identical in Training and Presentation apart from the product name. It uses only the standard library.

Version conflict: there is one `~/.claude/skills/harness-slides` and one `~/.claude/skills/harness-research` on a computer. Whichever studio installs last decides which version the others run. On 2026-10-15 both studios happened to pin the same versions again, but only because two PRs were made by hand to match. Nothing keeps them in step.

## 1.3 Decisions taken (overturn any of these)

| # | Decision | Rejected alternative | Change it if… |
|---|---|---|---|
| D1 | Import the three repositories with full history using `git filter-repo --to-subdirectory-filter`. | `git subtree add`, which keeps history but breaks `git log -- <path>` across the import. | `git filter-repo` cannot be installed. Fall back to `subtree`. |
| D2 | Import only `origin/main`. Land or re-create open PRs (presentation #5, blog #99) before or after the import. Stale branches stay readable in the archived repositories. | Import every branch. | A branch holds work you still want. |
| D3 | Studios use the core through a **symlink in the checkout**. The bundle build **copies** it in. | Install the core once at a shared path, or package it with pip. | Studios need to ship on different release cycles. |
| D4 | **One pins file**, `pins/companions.json`. Every studio is tested against it. | A pins file per studio. | Never. Studios share one install location, so one pin set is the only correct model. |
| D5 | The home page is its **own small server**. It starts each studio as a child process and hands it the key through `MARKETING_STUDIO_HANDOFF`. | One process serving every studio under `/training` and so on. | Later (§1.14). |
| D6 | The home page writes **only shared values**, to `studios-config.json`. Settings that belong to one studio stay in that studio. | The home page writes each studio's local settings. | — |
| D7 | Opening a studio for the first time after home set-up shows a **one-click "Start with your Marketing Studio settings"** confirmation. Studios do not set themselves up silently. | Fully automatic set-up. | You want zero clicks. This also loosens the shared rule that a team repository is never joined silently. |
| D8 | Add one optional shared value, `local.root`, the folder for work kept on this computer. Under it sit `trainings/`, `presentations/` and `blogs/`, mirroring the team-repository layout. | Each studio keeps its own default folder. | Studios must keep separate folders. |
| D9 | **One installer** with an opt-in per studio. One suite version. Each studio's own version is still shown. | Three installers. | Colleagues must install a single studio from its own repository. Per-studio zips are still built to cover this. |
| D10 | **Data folders stay where they are.** Only the code moves, to `~/.local/share/marketing-studio`. | Move data under one folder. | — |
| D11 | Archive the old repositories after cutover, each with a README pointing here. Releases come from this repository. | Keep the old repositories as release mirrors. | Blog Studio's published `releases/latest/download/...` links must keep working. Then keep `blog-studio` unarchived as a release mirror for one transition period. |
| D12 | Seed the core with only what the home page needs first: `errors`, `files`, `server`, `studios_config`, `computer`, `choices`. Extract the rest from the least drifted to the most. | Extract everything before building the home page. | — |

## 1.4 Repository layout

```text
marketing-studio/
  VERSION                          suite version; continues the studios' shared number (all three released 3.0.0 on 2026-10-15)
  README.md                        install + first run, for colleagues
  pins/companions.json             the one set of companion-skill pins (D4)
  core/studio_core/                shared Python, standard library only
    errors.py  files.py  server.py  studios_config.py  computer.py  choices.py
    (later: gitstate, team, hub, brand_source, companion, upkeep, agents, jobs)
  ui-kit/                          shared page files
    style.css  markdown.js         (later: shell.js with nav, settings cards, versions table)
  home/                            the Marketing Studio home page
    scripts/  marketing_studio.py  catalog.py  launcher.py  page.py  studio_core -> ../../core/studio_core
    page/     index.html  app.js  home.css  style.css -> ../../ui-kit/style.css
    tests/
  studios/
    training/                      was github.com/dbbaskette/training-studio (history kept)
    presentation/                  was github.com/dbbaskette/presentation-studio
    blog/                          was github.com/dbbaskette/blog-studio
  installer/                       one installer (from Training Studio's, which Presentation copies)
  scripts/
    build_bundles.py               builds per-studio and suite bundles, with links resolved
    ci/check_all.sh                every studio's checks, the core's and the home page's
  .github/workflows/ci.yml         one workflow with a job per part, filtered by path
  docs/
```

Inside each studio, links point at the shared files:

```text
studios/<x>/skills/<x>-studio/scripts/studio_core      -> ../../../../../core/studio_core
studios/<x>/skills/<x>-studio/scripts/desk/style.css   -> ../../../../../../ui-kit/style.css   (training, presentation)
studios/blog/skills/blog-studio/assets/management/style.css -> ../../../../../../ui-kit/style.css
studios/<x>/installer/companions.json                  -> ../../../pins/companions.json
```

`scripts/build_bundles.py` copies with links resolved (`shutil.copytree(symlinks=False)`). An installed bundle therefore never contains a link, and each bundle stands on its own, just as each studio's install does today.

## 1.5 The shared core

### What goes in, and in what order

The order goes from least drift and most need to most drift.

| Step | Module(s) | Today | Done when |
|---|---|---|---|
| Seed (Phase 3) | `errors` (`WorkspaceError`), `files` (`write_atomic`) | One copy in each studio's `workspace.py` | Each `workspace.py` re-exports the core's `WorkspaceError`, so every `except WorkspaceError` still catches. |
| Seed | `server` | Presentation's `server.py` (already "security base only"); Training's `desk.py`; Blog's own | Presentation imports it. Training's `desk.py` subclasses it (Phase 7). |
| Seed | `studios_config` | Three copies | All three import the core copy. `local` is added to `GROUPS`. |
| Seed | `computer` | Training and Presentation identical; Blog different | Training and Presentation import it. Blog keeps its own (Phase 7 decides). |
| Seed | `choices` (agents, efforts, outputs, share values, name and release patterns) | Constants in `runner/settings.py` | Home imports it. Studios import it in Phase 7. |
| UI | `ui-kit/style.css`, `ui-kit/markdown.js` | Byte-identical ×3 | Replaced by links; Blog's `training-studio-ui.json` is retired. |
| Phase 7 | `gitstate`, `team`, `hub` | Blog's `studio_sync`; Presentation's copies | One copy. |
| Phase 7 | `brand_source`, `brand` | Copied at 0881ce7 | One copy. The home page gains **Install brand skill**. |
| Phase 7 | `companion`, `upkeep`, installer pieces | Copied, with ~1,100 lines of drift | One copy, reading `pins/companions.json`. |
| Phase 7 (last) | Engine machinery: `jobs`, claims, turns, sharing | Presentation already split `jobs.py` out | Pipelines stay per studio; only the machinery is shared. |

Presentation Studio's `vendor.json` shrinks as each module moves. It is deleted when it is empty.

### Rules for core code

- Standard library only, Python 3.11 or newer, the same as the studios today.
- No product names in messages. Where a message needs one, it reads the module-level `PRODUCT`, which each studio's entry point sets.
- No paths relative to the core's own file. Because the core is reached through a link, `Path(__file__).resolve()` lands in `core/`. Anything a studio owns, such as its page folder, its pins or its data folder, is passed in by the studio.
- Tests for core code live in `core/tests/`. Each studio keeps the tests of its own use of the core.

## 1.6 One set of companion pins

`pins/companions.json` uses the shape the studios use today:

```json
{
  "schema": 1,
  "companions": {
    "harness-research": {"repository": "https://github.com/dbbaskette/harness-research-skill.git",
      "version": "0.8.1", "commit": "d58d20dbbd0a51173cd122f223351eea66168cb0",
      "sha256": "c9d15b03141585f86003ae3fb99b64bddd5b4639f4309a5e357d8cd1ff4db032",
      "stub": "bootstrap/SKILL.md", "installer": "scripts/install.mjs"},
    "harness-slides": { "...": "copied from training-studio/installer/companions.json at import" }
  }
}
```

To change a pin:

1. Edit `pins/companions.json`.
2. CI runs every studio's tests against the change.
3. Merge only when all of them pass.

Both studios already pin harness-research 0.8.1 and harness-slides 0.14.1. Phase 2 makes that one file instead of two copies that agree.

## 1.7 The home page

### Process model

```text
Terminal window "Marketing Studio"  (leave it open while you work)
  └─ home server   127.0.0.1:<H>   key KH, header X-Marketing-Studio-Token
       ├─ Training Studio      127.0.0.1:<T>   key KT  ← started on first "Open"
       ├─ Presentation Studio  127.0.0.1:<P>   key KP
       └─ Blog Studio          127.0.0.1:<B>   key KB
```

- The home page is started by `marketing-studio` (the command) or by `~/Applications/Open Marketing Studio.command`. It opens the browser on `http://127.0.0.1:<H>/#token=<KH>`.
- Pressing **Open** on a studio starts it once, if it is not already running.
  1. The home server makes a new key (`secrets.token_urlsafe(32)`).
  2. It starts the studio's own command with `MARKETING_STUDIO_HANDOFF={"token": KT, "home": "<home link with KH>"}`.
  3. It reads the studio's first line of output, which is its address and never its key.
  4. It answers the page with the studio's link, with the key in it.
  5. The page opens that link in a tab named `ms-<id>`.

  A second **Open** returns to the same tab.
- Each studio pops `MARKETING_STUDIO_HANDOFF` from its environment at once, so nothing it starts inherits it. It serves with the key it was given and does not open a browser itself. This mirrors the restart handoff Training and Presentation already use (`*_RESTART`).
- Closing the home window stops the home server. The home server sends `SIGTERM` to every studio it started and waits for each.
- A studio that is already running from an old per-studio launcher refuses to start; that is the existing `runner.pid` rule. The home page shows the studio's own sentence, for example "A runner is already serving on this computer…", and offers **Try again**.

### Security

The home server is the core `server.Page`, unchanged:

- It binds 127.0.0.1 only.
- `Host` must be its own address.
- The key travels in the URL fragment, and the token header is required on every `/api/` call.
- Each POST must carry one JSON object, from its own origin, of at most 64 KB.
- CSP is `default-src 'self'`, with `X-Frame-Options: DENY`, `no-referrer` and `no-store`.

The home page receives each studio's key only to hand it to the person's browser. It never logs the key and never writes it to disk.

Studios receive the home page's link, with its key, so that they can show a **Marketing Studio** link back. That is the same trust boundary: both are this person's own processes, and the key exists to keep other websites out, not this person's own programs.

### Home-page data

- **Shared values** are kept in `~/.config/studios-config.json`, written through `studio_core.studios_config.update`. That means the same lock, the same atomic merge and the same refusals as the studios use.
- **Home-only values** are kept in `~/.local/share/marketing-studio/home.json`, or the folder `MARKETING_STUDIO_DATA` names:

  ```json
  {"schema": 1, "enabled": ["training", "presentation", "blog"], "done": true}
  ```

- **Logs:** each studio's stderr goes to `~/.local/share/marketing-studio/logs/<id>.log`, which is overwritten on each start. Its last 12 lines are shown when the studio fails to open.

### API

| Method | Path | Body | Answer |
|---|---|---|---|
| GET | `/api/home` | — | `{"studios": [{"id", "name", "installed", "running"}], "shared": {...}, "shared_problem": str\|null, "setup": {"enabled": [...], "done": bool}, "computer": {...}\|null}` |
| POST | `/api/computer` | `{}` | `{"computer": {...}}`: a new look, reused for 60 s. The shape is `computer.check()`'s: `{checked_at, ready, assistants, wrong[], items[]}`. |
| POST | `/api/shared` | `{"changes": {...}, "seen": {...}}` | `{"shared": {...}}`. Refused with 409 if a changed value differs from what the form was shown (another studio changed it). |
| POST | `/api/setup` | `{"enabled": [...]}` and/or `{"done": true}` | `{"setup": {...}}` |
| POST | `/api/open` | `{"studio": "training"}` | `{"link": "http://127.0.0.1:<T>/#token=<KT>"}`, or 409 with the studio's own sentence |

Every value is checked against `studio_core.choices`. The values are:

| Value | Allowed |
|---|---|
| `assistant.agent` | `claude` or `codex` |
| `assistant.effort` | One of that agent's efforts |
| `output` | `google` or `pptx` |
| `share` | `decision` or `asked` |
| `brand.brand`, `brand.variant` | Match `WORD` |
| `brand.release` | Matches `RELEASE` |
| `person.name` | At most 100 characters |
| Repository addresses | Checked by `studios_config` itself, which refuses an address carrying credentials |

### Screens

**First run.** There are six steps. Each step saves when the person presses **Next**, so leaving halfway keeps what was answered. Each step shows the values already in `studios-config.json` as its starting values. This matters for a colleague who has already used a studio, because their answers carry over.

```text
┌ Marketing Studio ──────────────────────────────────────────────── step 1 of 6 ┐
│ Welcome. Which studios will you use?                                           │
│   [x] Training Studio       turn a topic into researched training              │
│   [x] Presentation Studio   slide decks in your brand                          │
│   [x] Blog Studio           blogs that sound like you                          │
│                                                                    [ Next → ]  │
└────────────────────────────────────────────────────────────────────────────────┘
┌ step 2 of 6 · This computer ───────────────────────────────────────────────────┐
│  ✓ Python 3.12          ✓ git, with your name and email     ✓ Node 22          │
│  ✓ Claude Code, signed in, reaches api.anthropic.com                           │
│  ✗ harness-slides is missing   → it is installed with Marketing Studio; run:   │
│                                  marketing-studio check --repair               │
│  ○ gcloud (optional unless you deliver to Google)                              │
│                                          [ Look again ]   [ Next → ]           │
└────────────────────────────────────────────────────────────────────────────────┘
┌ step 3 of 6 · You and your assistant ──────────────────────────────────────────┐
│  Your name   [______________]   (shown as the author)                          │
│  Assistant   (•) Claude Code  ( ) Codex                                        │
│  Model       [opus________]     Reasoning  [high ▾]                            │
└────────────────────────────────────────────────────────────────────────────────┘
┌ step 4 of 6 · Where your work is kept ─────────────────────────────────────────┐
│  (•) On this computer   folder [~/Studios________]                             │
│       trainings/, presentations/ and blogs/ go inside it                       │
│  ( ) In a team repository   address [https://github.com/acme/studios.git]      │
│       branch [main]   share: (•) after each decision  ( ) only when I ask      │
└────────────────────────────────────────────────────────────────────────────────┘
┌ step 5 of 6 · Your brand ──────────────────────────────────────────────────────┐
│  Brand skill repository [https://github.com/acme/brand-skill.git]              │
│  Release [v1.4.0]    Brand [acme]   Variant [light]                            │
│  Install or upgrade it from any studio's Status page.   (Install here: Phase 7)│
│                                                     [ Skip for now ] [ Next → ]│
└────────────────────────────────────────────────────────────────────────────────┘
┌ step 6 of 6 · Deliver as ──────────────────────────────────────────────────────┐
│  (•) Google Slides and Docs   ( ) PowerPoint and Word files                    │
│                                                               [ Finish → ]     │
└────────────────────────────────────────────────────────────────────────────────┘
```

**The launch pad**, after set-up and on every later visit:

```text
┌ Marketing Studio ─────────────────────────── Settings · This computer · Versions ┐
│ ┌ Training Studio ──────┐ ┌ Presentation Studio ───┐ ┌ Blog Studio ────────────┐ │
│ │ Running               │ │ Not running            │ │ Not installed           │ │
│ │ 2 trainings need you* │ │ 1 deck needs you*      │ │ Add it with the         │ │
│ │ [ Open ]              │ │ [ Open ]               │ │ installer               │ │
│ └───────────────────────┘ └────────────────────────┘ └─────────────────────────┘ │
│ Shared settings                                                      [ Change ] │
│   Claude Code · opus · high   │ Team: github.com/acme/studios (main), each decision │
│   Brand: acme / light @ v1.4.0│ Deliver as: Google                                │
└──────────────────────────────────────────────────────────────────────────────────┘
* "needs you" counts arrive in Phase 6 (§1.9); until then a card shows Running / Not running.
```

- **Settings** reuses steps 3–6 as forms.
- **This computer** is step 2.
- **Versions** arrives in Phase 5 (§1.10).

**What a studio shows when opened from home** (Phase 6):

- A **Marketing Studio** link at the top of its sidebar, back to the `ms-home` tab.
- The first time it is opened, if it is not yet set up and the shared settings cover what it needs, the usual set-up form is replaced by one card: "Start with your Marketing Studio settings". The card lists the values and has one button. Local-only choices use their defaults: limits, previews, notifications. Those can be changed later in the studio's Settings.

## 1.8 Shared settings: one addition

`studios-config.json` gains one optional group (D8):

```json
{"local": {"root": "~/Studios"}}
```

- When a studio is kept on this computer and `local.root` is set, the studio suggests:
  - `<root>/trainings` for Training Studio,
  - `<root>/presentations` for Presentation Studio,
  - `<root>/blogs` for Blog Studio, passed as `--root`.
- Existing workspaces never move. The value only changes what is suggested for a new one.
- `schema` stays at 1. Studios ignore keys they do not know, so this addition is safe for older installs.
- The core `studios_config.GROUPS` gains `'local'`.
- `docs/shared-studios.md` (in Presentation, and later the root `docs/`) documents the new group.

## 1.9 Changes inside the studios

| Change | Training | Presentation | Blog | Phase |
|---|---|---|---|---|
| Accept `MARKETING_STUDIO_HANDOFF`: use the key, do not open a browser, keep `home` | `runner/studio.py: handed_over()` | Same | `start_studio.py`, `management.py` (key creation, ~L1824 on origin/main) | 4 |
| Show the **Marketing Studio** link when `home` was handed over | `describe()` gains `home`; `app.js` sidebar | Same | `/api/...` state gains `home`; `runner.js` | 6 |
| "Start with your Marketing Studio settings" quick start (D7) | `setup.py` and `app.js` | Same | `blog_runner.py` and `runner.js` | 6 |
| Use `local.root` in the suggested workspace | `setup.suggested()` | Same | Launcher passes `--root` | 6 |
| `studio status` gains `summary: {"waiting": n, "working": n}` for home cards | `engine.status()` | Same | `start_studio.py status --json` (new) | 6 |
| Upgrade buttons defer to Marketing Studio when installed as part of the suite | `upkeep.py` reads the suite's `installation.json` | Same | — (Blog has no upgrade view) | 5 |

## 1.10 Installer, bundles and existing installs

**Bundles.** `scripts/build_bundles.py VERSION` writes the following, with links resolved and without `tests/`, `docs/` or CI files:

```text
dist/
  marketing-studio-<v>/   home/  training-studio/  presentation-studio/  blog-studio/  installer/  VERSION
  marketing-studio-<v>.zip
  training-studio-<v>.zip  presentation-studio-<v>.zip  blog-studio-<v>.zip     (one studio each)
```

Each studio's own `validate_package.py` runs against its bundle, and the build fails if any budget fails.

**Install layout** (D10):

```text
~/.local/share/marketing-studio/
  versions/<VERSION>-<hash>/     a bundle
  current -> versions/...
  installation.json              suite version, history, enabled studios
  home.json  logs/  companions/<name>/<commit12>/  backups/
  marketing-studio               the command: opens the home page, or `open <id>`, `check`, `rollback`, `uninstall`
~/.claude/skills/<x>-studio  -> ~/.local/share/marketing-studio/current/<x>-studio     (and ~/.agents/skills/…)
~/Applications/Open Marketing Studio.command
```

**Existing installs.** The installer migrates each studio it finds installed standalone, in these steps:

1. **Refuses while any studio is serving.** This is the existing `runner.pid` and Blog lock check.
2. **Renames the old code pointer.** `~/.local/share/<x>-studio/current` becomes `current.pre-suite`. The old `installation.json` gains `"moved_to": "marketing-studio"`, so an old runner's upkeep cannot point the skill links back at the old code.
3. **Points the skill links at the suite.**
4. **Replaces `Open <X> Studio.command`** with a launcher that runs `marketing-studio open <id>`.
5. **Leaves the data alone.** `runner.json`, workspaces, jobs, Blog's `~/blogs/.blog-studio` and `studios-config.json` are not touched.

To go back:

- `marketing-studio rollback` moves `current` back within the suite.
- `marketing-studio uninstall --restore-standalone` reverses each migration, renaming `current.pre-suite` back to `current` and restoring the links.

**Upgrades.** The suite looks for new release tags `v<VERSION>` once a day, as Training Studio does today. A studio's own **Upgrade** button, when that studio is installed as part of the suite, says "Update from Marketing Studio" and links to the home page's Versions view.

## 1.11 Repository migration

**Before the freeze** (Phase 0). At 17:38 on 2026-10-15:

- training-studio had an unpushed branch.
- presentation-studio had PR #5 open, four worktrees and an unpushed fix.
- blog-studio had PR #99 open and two worktrees.
- Local `main` was behind `origin/main` in all three.

By the end of 2026-10-15 every open PR was merged, every checkout was on its latest `main`, and the worktrees were removed. See Task 0.1 for the record.

**Import** (D1, D2):

1. Mirror-clone each repository fresh, never from the working copies.
2. Rewrite each clone into `studios/<id>/` with `git filter-repo`, prefixing tags (for example `blog-studio/v2.1.0`).
3. Merge each into this repository with `--allow-unrelated-histories`.

The import changes no behaviour. The first acceptance test is that every studio's own `check.sh` or `run_tests.py` passes from its new folder.

**Cutover** (Phase 8):

1. Create `github.com/dbbaskette/marketing-studio`.
2. Transfer open issues with `gh issue transfer`.
3. Push one last README commit to each old repository pointing here, then archive it (D11).
4. Update the install docs.

## 1.12 Errors: what the person sees

| Situation | What happens |
|---|---|
| `studios-config.json` unreadable or invalid | Home shows the core's own sentence ("…so built-in defaults are used…"). Every save is refused until the file can be read. The file is never overwritten. |
| Another studio changed a value while a form was open | 409 with "X was changed in another studio while this was open, so nothing was saved. Look again." The form reloads. |
| A studio is not installed | Its card says "Not installed" and how to add it (`installer/install.sh --studios <id>`). **Open** is not offered. |
| A studio is already running from its old launcher | Its own refusal is shown, with **Try again**. |
| Marketing Studio is already open, and the command is run again | It refuses with "Marketing Studio is already open (process N). Use its page, or close its window before opening it again." The check is `home.pid`, the same rule the studios follow. |
| A studio prints nothing within 60 s, or exits | It is ended. "<Name> did not open." followed by the last 12 lines of its log. |
| A studio prints an address that is not `http://127.0.0.1:…` | It is ended and refused. It never becomes a link. |
| A check item is missing | Shown with its `fix` text. **Next** is still allowed; each studio refuses at the point it actually needs the missing thing, as it does today. |
| The home server is stopped (window closed) | The page says the home page is not running and how to open it again. Studios started by it stop too. |

## 1.13 Testing

- **Per studio:** each studio's existing suite runs unchanged from `studios/<id>/` (Phase 1 acceptance), then against the shared core and pins on every change.
- **Core:** `core/tests/` covers:
  - the moved tests for `studios_config`, `server` security and `computer`,
  - the core's own `local` group,
  - the `PRODUCT` wording.
- **Home:**
  - The launcher, against a fake studio script: a handed key, an error line, silence and timeout, an exit, a bad address, stop.
  - `page.py`: every API route through the real `Desk` on port 0, the security rules (no key, wrong Host, wrong Origin) and stale guards.
  - The page JS, through the studios' `page_harness.js` approach, in Phase 6.
- **Bundles:** `build_bundles.py` must produce bundles with no symlinks, in which each studio's `validate_package.py` passes.
- **Installer:** adapted from Training Studio's `test_installer.py`, plus migration tests on a fake home folder holding a standalone install (rename, links and launchers, then a restore).
- **CI:** `.github/workflows/ci.yml` runs Ubuntu and macOS × Python 3.11 and 3.13. The jobs are core, home and each studio. A change under `core/`, `ui-kit/` or `pins/` runs **every** job. The Tart verify workflows move to the root unchanged, one per studio.

## 1.14 Later (not in this plan)

- **One origin.** One server serves `/`, `/training/`, `/presentations/` and `/blogs/`, giving one key, one tab and one nav shell. This needs each studio's `app.js` to use relative API paths and one token header. Worth it after Phase 7 has made the server one copy.
- **A shared page shell:** `ui-kit/shell.js`, with nav, Settings, Versions and This computer cards, replacing the copies in the three `app.js` files.
- **Home "needs you" notifications** across studios.

## 1.15 Open questions

1. Should Blog Studio keep `blog-studio` unarchived as a release mirror (D11)? Its README links to `releases/latest/download/blog-studio-installer.zip`.
2. Is `~/Studios` the right default for `local.root`, or should it be `~/Marketing Studio`?
3. Who besides you installs these today? That decides how loud the migration notice in the installer needs to be.
4. What is the first suite release's number? Choose 3.1.0 if moving into the suite is seamless for existing installs (§1.10 keeps data and can be undone). Choose 4.0.0 if the new install location and the single installer should count as a breaking change.

---

# Part 2: Implementation plan

# Marketing Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**

- Move Training, Presentation and Blog Studio into one repository with a shared core and one pin set.
- Add a home page that sets the shared values once and opens each studio.

**Architecture:**

- The three repositories are imported with history under `studios/`.
- Shared Python lives in `core/studio_core/` and shared page files in `ui-kit/`. Studios reach both through symlinks in the checkout, and bundles copy them in.
- The home page is a small server built on the core server. It writes `studios-config.json` and starts each studio as a child process with a handed-over key.

**Tech stack:** Python 3.11+ (standard library only), vanilla JS/CSS (CSP `default-src 'self'`), `unittest`, git and `git-filter-repo`, GitHub Actions, POSIX shell.

**Conventions to follow** (from the studios):

- Docstrings start with "What a caller needs to know".
- Refusals are `WorkspaceError` with one plain sentence.
- Tests use `unittest`.
- Commands print one JSON line.
- Never add a dependency outside the standard library.

---

## Phase 0: Pre-flight (manual, with the user)

### Task 0.1: Land or park in-flight work

- [x] **Step 1: Check whether other work is in flight in a studio.** Done 2026-10-15. Six worktrees were found, all merged and clean, with their sessions idle, and all six were removed. `training-studio/.worktrees` held only empty folders and was removed too. Each repository now has only its main checkout. To check again, run each command and expect only the main checkout. Extra worktrees mean other work is in flight:

  ```bash
  git -C ../training-studio worktree list
  ```
  ```bash
  git -C ../presentation-studio worktree list
  ```
  ```bash
  git -C ../blog-studio worktree list
  ```

  Ask the user before going on if one is active.
- [x] **Step 2: training-studio.** Done 2026-10-15. `claude/pin-companions-0.8.1` was pushed and merged as [dbbaskette/training-studio#75](https://github.com/dbbaskette/training-studio/pull/75), merge commit `7867239`. The full suite passed locally first (1,992 OK, 61 skipped). CI was still pending at merge time. Local `main` was fast-forwarded.
- [x] **Step 3: presentation-studio.** Done 2026-10-15. Three PRs were merged:
  - PR #5, merged by its own session (`d6e3aba`);
  - PR #6, reviewing stops (`bcee5d8`);
  - [dbbaskette/presentation-studio#7](https://github.com/dbbaskette/presentation-studio/pull/7), which keeps the upgrade test off the network (`943ad71`).

  Presentation has no CI, so each was gated by a local run: 1,229 tests OK (29 skipped) and `validate_package` OK, with no network calls once #7 was in.
- [x] **Step 4: blog-studio PR #99.** Done 2026-10-15. Merged as `a15b8bd` after four green Tart verify jobs and GitGuardian. Blog's hosted `ci.yml` is turned off, so Task 1.5 must run Blog's Tart verify or turn hosted checks back on.
- [ ] **Step 5: Freeze.** At the end of 2026-10-15 all three were released as `v3.0.0`, and the `main` commits were training `de20a08`, presentation `edf565a` and blog `44f59e5`, with no open PRs. Releases: [training v3.0.0](https://github.com/dbbaskette/training-studio/releases/tag/v3.0.0), [presentation v3.0.0](https://github.com/dbbaskette/presentation-studio/releases/tag/v3.0.0) and [blog v3.0.0](https://github.com/dbbaskette/blog-studio/releases/tag/v3.0.0). Re-run the command below on the day of the import, because these will move. Tell the user that from here until Phase 1 Task 1.4, nothing merges to any of the three `main` branches. Record each `origin/main` commit:

  ```bash
  for r in training-studio presentation-studio blog-studio; do git -C ../$r fetch -q origin && echo "$r $(git -C ../$r rev-parse origin/main)"; done
  ```

  Paste the output into `docs/import-record.md` (created in Task 1.3).

### Task 0.2: Install `git-filter-repo`

- [ ] **Step 1:** Install it:

  ```bash
  python3 -m pip install --user git-filter-repo
  ```
- [ ] **Step 2:** Confirm it runs:

  ```bash
  git filter-repo --version
  ```

  Expected: a version hash is printed. If this fails, fall back to D1's alternative, `git subtree add --prefix=studios/<id> <url> main`, in Task 1.3.

---

## Phase 1: One repository, no behaviour change

### Task 1.1: Start the repository

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `VERSION`

- [ ] **Step 1: Write `.gitignore`:**

  ```gitignore
  .DS_Store
  __pycache__/
  *.pyc
  node_modules/
  .claude/worktrees/
  .claude/.cc-writes/
  .claude/settings.local.json
  .worktrees/
  dist/
  build/
  ```

- [ ] **Step 2: Write `VERSION`** with the single line `3.0.0`. Training, Presentation and Blog Studio were all released as 3.0.0 on 2026-10-15, and the suite carries that number on.
- [ ] **Step 3: Write `README.md`:**

  ```markdown
  # Marketing Studio

  Training Studio, Presentation Studio and Blog Studio, in one place. Install once, set up once on
  one page, then open whichever studio you need.

  Work in progress: see docs/marketing-studio-spec-and-plan.md.
  ```

- [ ] **Step 4: Commit:**

  ```bash
  git init -b main && git add .gitignore README.md VERSION docs/marketing-studio-spec-and-plan.md && git commit -m "Start Marketing Studio with its design and plan"
  ```

### Task 1.2: Prepare each import in a scratch folder

**Files:** none in the repository. Work goes in `$TMPDIR/ms-import/`.

- [ ] **Step 1: Fresh clones**, never the working copies:

  ```bash
  mkdir -p "$TMPDIR/ms-import" && cd "$TMPDIR/ms-import" && for r in training presentation blog; do git clone --no-local "https://github.com/dbbaskette/$r-studio.git" "$r"; done
  ```

- [ ] **Step 2: Rewrite each into its folder and prefix its tags:**

  ```bash
  cd "$TMPDIR/ms-import" && for r in training presentation blog; do (cd "$r" && git filter-repo --force --to-subdirectory-filter "studios/$r" --tag-rename ":$r-studio/"); done
  ```

- [ ] **Step 3: Check one rewrite.** Run:

  ```bash
  git -C "$TMPDIR/ms-import/blog" ls-tree --name-only HEAD
  ```

  Expected: only `studios`. Then run:

  ```bash
  git -C "$TMPDIR/ms-import/blog" tag | head -3
  ```

  Expected: names starting `blog-studio/`.

### Task 1.3: Merge the three histories

**Files:**
- Create: `docs/import-record.md`

- [ ] **Step 1:** Merge each rewritten history:

  ```bash
  for r in training presentation blog; do git remote add "import-$r" "$TMPDIR/ms-import/$r" && git fetch -q --tags "import-$r" && git merge --allow-unrelated-histories --no-edit -m "Import $r-studio with its history" "import-$r/main"; done
  ```

- [ ] **Step 2: Write `docs/import-record.md`:**

  ```markdown
  # Import record

  Imported 2026-10-15 with git filter-repo --to-subdirectory-filter, tags prefixed with <name>-studio/.

  | Studio | From | Commit |
  |---|---|---|
  | Training | https://github.com/dbbaskette/training-studio | <paste from Task 0.1 Step 5> |
  | Presentation | https://github.com/dbbaskette/presentation-studio | <paste> |
  | Blog | https://github.com/dbbaskette/blog-studio | <paste> |
  ```

  Fill each `<paste>` with the hash recorded in Task 0.1 Step 5. They are facts to copy, not decisions.

- [ ] **Step 3: Remove the import remotes and commit:**

  ```bash
  for r in training presentation blog; do git remote remove "import-$r"; done && git add docs/import-record.md && git commit -m "Record where each studio was imported from"
  ```

### Task 1.4: Prove nothing changed

- [ ] **Step 1: Training.** Run:

  ```bash
  bash studios/training/scripts/ci/check.sh python3
  ```

  Expected: the test summary shows no failures and `validate_package.py` passes.
- [ ] **Step 2: Presentation.** Run:

  ```bash
  cd studios/presentation && python3 scripts/ci/run_tests.py && python3 skills/presentation-studio/scripts/validate_package.py
  ```

  Expected: no failures.
- [ ] **Step 3: Blog.** Run:

  ```bash
  cd studios/blog && python3 -m pip install -r requirements-dev.txt && bash scripts/ci/check.sh "$(command -v python3)" "$TMPDIR/blog-checks"
  ```

  Expected: no failures.
- [ ] **Step 4: If a test depends on being at the repository root**, for example `git rev-parse --show-toplevel`, fix that test to use its own folder. Commit each fix as `Find <studio>'s own folder rather than the repository's top` and re-run the step that failed.
- [ ] **Step 5: Lift the freeze** (Task 0.1 Step 5). From now on, studio work happens here.

### Task 1.5: One CI workflow

**Files:**
- Create: `scripts/ci/check_all.sh`
- Create: `.github/workflows/ci.yml`
- Move: `studios/training/.github/workflows/verify-tart.yml` → `.github/workflows/verify-tart-training.yml`
- Move: `studios/blog/.github/workflows/verify-tart.yml` → `.github/workflows/verify-tart-blog.yml`
- Delete: `studios/training/.github/workflows/ci.yml`, `studios/blog/.github/workflows/ci.yml` (GitHub ignores workflows that are not at the root)

- [ ] **Step 1: Write `scripts/ci/check_all.sh`:**

  ```bash
  #!/bin/bash
  # Every check, or the named parts: core home training presentation blog.
  # Usage: check_all.sh [python] [part ...]
  set -euo pipefail
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
  python="${1:-python3}"; shift || true
  parts=("$@"); [ ${#parts[@]} -gt 0 ] || parts=(core home training presentation blog)
  for part in "${parts[@]}"; do
    printf '\n== %s ==\n' "$part"
    case "$part" in
      core|home)
        if [ -d "$root/$part/tests" ]; then (cd "$root/$part" && "$python" -m unittest discover -s tests -t .)
        else echo "no tests yet"; fi ;;
      training) bash "$root/studios/training/scripts/ci/check.sh" "$python" ;;
      presentation) (cd "$root/studios/presentation" && "$python" scripts/ci/run_tests.py && "$python" skills/presentation-studio/scripts/validate_package.py) ;;
      blog) bash "$root/studios/blog/scripts/ci/check.sh" "$python" "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/blog-studio-checks" ;;
      *) echo "Unknown part: $part" >&2; exit 2 ;;
    esac
  done
  ```

- [ ] **Step 2: Write `.github/workflows/ci.yml`:**

  ```yaml
  name: CI
  on:
    push:
      branches: [main]
    pull_request:
  permissions:
    contents: read
  concurrency:
    group: ci-${{ github.ref }}
    cancel-in-progress: true
  jobs:
    changes:
      runs-on: ubuntu-latest
      outputs:
        parts: ${{ steps.pick.outputs.parts }}
      steps:
        - uses: actions/checkout@v4
          with: { fetch-depth: 0 }
        - id: pick
          shell: bash
          run: |
            base="${{ github.event.pull_request.base.sha || github.event.before }}"
            changed="$(git diff --name-only "$base" HEAD 2>/dev/null || echo ALL)"
            all='["core","home","training","presentation","blog"]'
            if [ "$changed" = ALL ] || grep -qE '^(core|ui-kit|pins|scripts|\.github)/' <<<"$changed"; then
              echo "parts=$all" >> "$GITHUB_OUTPUT"; exit 0; fi
            parts=()
            grep -q '^home/' <<<"$changed" && parts+=('"home"')
            for s in training presentation blog; do grep -q "^studios/$s/" <<<"$changed" && parts+=("\"$s\""); done
            [ ${#parts[@]} -gt 0 ] || parts=('"core"')
            echo "parts=[$(IFS=,; echo "${parts[*]}")]" >> "$GITHUB_OUTPUT"
    test:
      needs: changes
      name: ${{ matrix.part }} (${{ matrix.os }}, Python ${{ matrix.python }})
      runs-on: ${{ matrix.os }}
      timeout-minutes: 30
      strategy:
        fail-fast: false
        matrix:
          part: ${{ fromJSON(needs.changes.outputs.parts) }}
          os: [ubuntu-latest, macos-latest]
          python: ['3.11', '3.13']
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '${{ matrix.python }}' }
        - if: matrix.part == 'blog'
          run: python -m pip install -r studios/blog/requirements-dev.txt
        - env: { BLOG_STUDIO_REQUIRE_LINT: '1' }
          run: bash scripts/ci/check_all.sh "$(command -v python)" "${{ matrix.part }}"
  ```

- [ ] **Step 3: Move the Tart workflows.** In each moved workflow, prefix every path the workflow names with `studios/<id>/`. Read each file and change only its paths.
- [ ] **Step 4: Run `bash scripts/ci/check_all.sh python3` locally.** Expected: every part passes; core and home print "no tests yet".
- [ ] **Step 5: Commit:**

  ```bash
  git add -A .github scripts studios/training/.github studios/blog/.github && git commit -m "Run every studio's checks from one workflow"
  ```

---

## Phase 2: One set of pins

### Task 2.1: `pins/companions.json` replaces the per-studio copies

**Files:**
- Create: `pins/companions.json` (copy of `studios/training/installer/companions.json`, which has harness-research 0.8.1 once Task 0.1 Step 2 has landed)
- Replace with symlinks: `studios/training/installer/companions.json`, `studios/presentation/installer/companions.json`

- [ ] **Step 1: Copy and link:**

  ```bash
  mkdir -p pins && cp studios/training/installer/companions.json pins/companions.json && for s in training presentation; do ln -sf ../../../pins/companions.json "studios/$s/installer/companions.json"; done
  ```

- [ ] **Step 2: Check the pins.** Run:

  ```bash
  python3 -c "import json;d=json.load(open('pins/companions.json'));print({k:v['version'] for k,v in d['companions'].items()})"
  ```

  Expected: `{'harness-research': '0.8.1', 'harness-slides': '0.14.1'}`.
- [ ] **Step 3: Run the checks:**

  ```bash
  bash scripts/ci/check_all.sh python3 training presentation
  ```

  - Expected: both pass.
  - If Presentation's installer or package tests refuse a symlinked `companions.json` (they may check for links), change that check to accept a link whose target resolves inside the repository's `pins/` folder. Add a test case `test_pins_link_is_followed` to `studios/presentation/tests/test_installer.py` that builds a temporary tree with a link and asserts the pins are read through it.
- [ ] **Step 4: Commit:**

  ```bash
  git add -A pins studios && git commit -m "Pin the companion skills once for every studio"
  ```

---

## Phase 3: Seed the shared core

### Task 3.1: `errors` and `files`

**Files:**
- Create: `core/studio_core/__init__.py`, `core/studio_core/errors.py`, `core/studio_core/files.py`
- Create: `core/tests/__init__.py`, `core/tests/test_files.py`

- [ ] **Step 1: Write the failing test** in `core/tests/test_files.py`:

  ```python
  import os
  import tempfile
  import unittest
  from pathlib import Path

  from studio_core.errors import WorkspaceError
  from studio_core.files import write_atomic


  class WriteAtomicTests(unittest.TestCase):
      def test_writes_whole_file_and_leaves_no_temporary(self):
          with tempfile.TemporaryDirectory() as folder:
              target = Path(folder) / 'deep' / 'home.json'
              write_atomic(target, '{"schema": 1}\n')
              self.assertEqual(target.read_text(encoding='utf-8'), '{"schema": 1}\n')
              self.assertEqual(sorted(os.listdir(target.parent)), ['home.json'])

      def test_workspace_error_is_an_exception_with_a_sentence(self):
          self.assertEqual(str(WorkspaceError('Say it plainly.')), 'Say it plainly.')


  if __name__ == '__main__':
      unittest.main()
  ```

- [ ] **Step 2: Run it.**

  ```bash
  cd core && python3 -m unittest discover -s tests -t . -v
  ```

  Expected: FAIL with `ModuleNotFoundError: No module named 'studio_core'`.
- [ ] **Step 3: Write the modules.**

  `core/studio_core/__init__.py`:

  ```python
  """What every studio shares. Standard library only; nothing here names a studio.

  A studio reaches this package through a link beside its own scripts in a checkout of the
  repository, and through a copy once it is installed. Nothing here finds a file by its own
  path: what belongs to a studio is handed in by the studio.
  """
  ```

  `core/studio_core/errors.py`:

  ```python
  """The refusal a person reads.

  What a caller needs to know
  ---------------------------
      raise WorkspaceError('One sentence a person can read as it is.')

  Every studio's own `workspace.WorkspaceError` is this class, so a refusal raised here is
  caught wherever a studio catches its own.
  """


  class WorkspaceError(Exception):
      """A refusal or failure, said in one sentence a person can read as it is."""
  ```

  `core/studio_core/files.py`:

  ```python
  """Files written so that a reader sees the old one or the new one, never half of either.

  What a caller needs to know
  ---------------------------
      write_atomic(path, text)     # makes the folder if need be
  """
  from __future__ import annotations

  import os
  import tempfile
  from pathlib import Path


  def write_atomic(path: Path, text: str) -> None:
      """Write text so a reader sees the old file or the new one, never half of either."""
      path.parent.mkdir(parents=True, exist_ok=True)
      handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.')
      try:
          with os.fdopen(handle, 'w', encoding='utf-8') as out:
              out.write(text)
          os.replace(temporary, path)
      except BaseException:
          Path(temporary).unlink(missing_ok=True)
          raise
  ```

  Also create an empty `core/tests/__init__.py`.

- [ ] **Step 4: Run it.** Use the same command as Step 2. Expected: 2 tests, OK.
- [ ] **Step 5: Make each studio's `WorkspaceError` the core's.** First link the core in:

  ```bash
  for s in training presentation blog; do ln -s ../../../../../core/studio_core "studios/$s/skills/$s-studio/scripts/studio_core"; done
  ```

  Then, in `studios/presentation/skills/presentation-studio/scripts/workspace.py` and `studios/training/skills/training-studio/scripts/workspace.py`, replace the `class WorkspaceError(Exception): ...` block with:

  ```python
  from studio_core.errors import WorkspaceError  # noqa: F401  one refusal for every studio
  ```

  Replace their `write_atomic` the same way, with `from studio_core.files import write_atomic  # noqa: F401`. Do this only if its body is the one shown in Step 3; if a studio's differs, leave that studio's copy and note it in `vendor.json`'s successor list (Task 7.0).
- [ ] **Step 6: Run the studio checks:**

  ```bash
  bash scripts/ci/check_all.sh python3 core training presentation blog
  ```

  - Expected: all pass.
  - If a studio's `validate_package.py` or package test refuses the `studio_core` link, teach it to accept a link whose resolved target lies inside the repository's `core/` folder. Add a test for that, then re-run.
- [ ] **Step 7: Commit:**

  ```bash
  git add -A core studios && git commit -m "Share one WorkspaceError and write_atomic across the studios"
  ```

### Task 3.2: `studios_config` in the core, with `local`

**Files:**
- Create: `core/studio_core/studios_config.py` (from `studios/presentation/skills/presentation-studio/scripts/studios_config.py`)
- Create: `core/studio_core/addresses.py`
- Create: `core/tests/test_studios_config.py` (from `studios/presentation/tests/test_studios_config.py`)
- Modify: Presentation `studios_config.py` (becomes a re-export), Training `runner/studios_config.py` (same), Blog `studios_config.py` (same, on origin/main 2.1.0)
- Modify: `studios/presentation/skills/presentation-studio/scripts/hub.py` (import `ADDRESS_WITH_SECRET` from the core)

- [ ] **Step 1: Write the failing test for the new group** in `core/tests/test_local_root.py`:

  ```python
  import json
  import os
  import tempfile
  import unittest
  from pathlib import Path

  from studio_core import studios_config


  class LocalRootTests(unittest.TestCase):
      def setUp(self):
          self.folder = tempfile.TemporaryDirectory()
          self.file = Path(self.folder.name) / 'studios-config.json'
          os.environ['STUDIOS_CONFIG'] = str(self.file)

      def tearDown(self):
          os.environ.pop('STUDIOS_CONFIG', None)
          self.folder.cleanup()

      def test_local_root_is_saved_and_read(self):
          studios_config.update({'local': {'root': '~/Studios'}})
          found, problem = studios_config.read()
          self.assertIsNone(problem)
          self.assertEqual(found['local'], {'root': '~/Studios'})

      def test_other_keys_keep_their_bytes(self):
          self.file.write_text('{\n  "schema": 1,\n  "share": "asked",\n  "zzz": [1, 2]\n}\n', encoding='utf-8')
          studios_config.update({'local': {'root': '~/Studios'}})
          text = self.file.read_text(encoding='utf-8')
          self.assertIn('"zzz": [1, 2]', text)
          self.assertEqual(json.loads(text)['share'], 'asked')

      def test_message_names_the_product(self):
          studios_config.PRODUCT = 'Marketing Studio'
          self.file.write_text('not json', encoding='utf-8')
          _, problem = studios_config.read()
          self.assertIn('Marketing Studio', problem)


  if __name__ == '__main__':
      unittest.main()
  ```

- [ ] **Step 2: Run it.**

  ```bash
  cd core && python3 -m unittest tests.test_local_root -v
  ```

  Expected: FAIL with `ImportError: cannot import name 'studios_config'`.
- [ ] **Step 3: Move the module and make three edits.**

  ```bash
  cp studios/presentation/skills/presentation-studio/scripts/studios_config.py core/studio_core/studios_config.py
  ```

  In `core/studio_core/studios_config.py`, make these edits:

  - Replace `import hub` and `from workspace import WorkspaceError` with:

    ```python
    from studio_core.addresses import ADDRESS_WITH_SECRET
    from studio_core.errors import WorkspaceError
    ```

    Replace `hub.ADDRESS_WITH_SECRET` with `ADDRESS_WITH_SECRET`.
  - Replace `GROUPS = ('team', 'person', 'assistant', 'brand')` with:

    ```python
    GROUPS = ('team', 'person', 'assistant', 'brand', 'local')   # keys whose value is an object
    PRODUCT = 'This studio'     # each studio's entry point sets its own name
    ```

  - Replace every literal `Presentation Studio` in a message with `{PRODUCT}` inside an f-string, built when the message is made. For example, change the module constant `USING = (', so Presentation Studio uses…')` into a function:

    ```python
    def using() -> str:
        return (f', so {PRODUCT} uses its built-in defaults for the values every studio '
                'shares until it can be read.')
    ```

    Update its two callers (`_unreadable` and the `problem.removesuffix(USING)` sites) to call `using()`. Read the module's docstring line naming the shape and add `"local": {"root"}`.

  Then move the secret-address pattern:

  ```bash
  grep -n 'ADDRESS_WITH_SECRET' studios/presentation/skills/presentation-studio/scripts/hub.py
  ```

  Copy that one `ADDRESS_WITH_SECRET = re.compile(...)` line, with its comment, into a new `core/studio_core/addresses.py`:

  ```python
  """Repository addresses: what may and may not be written down.

  What a caller needs to know
  ---------------------------
      ADDRESS_WITH_SECRET.match(address)    # an address carrying a password or token
  """
  import re

  # <paste the exact ADDRESS_WITH_SECRET line from hub.py here, unchanged>
  ```

  The paste is a copy of an existing line, not a decision.

  In `hub.py`, replace that line with `from studio_core.addresses import ADDRESS_WITH_SECRET  # noqa: F401`.

- [ ] **Step 4: Move the tests.**

  ```bash
  cp studios/presentation/tests/test_studios_config.py core/tests/test_studios_config.py
  ```

  - In the copy, change `import studios_config` to `from studio_core import studios_config`.
  - Change any `from workspace import WorkspaceError` to `from studio_core.errors import WorkspaceError`.
  - Change expected strings that contain `Presentation Studio` to set `studios_config.PRODUCT = 'Presentation Studio'` in `setUp`.
- [ ] **Step 5: Turn each studio's copy into a re-export.** Find Blog's copy with:

  ```bash
  git ls-files studios/blog | grep studios_config
  ```

  It came with 2.1.0 on `origin/main`. Replace the whole body of Presentation's `skills/presentation-studio/scripts/studios_config.py`, Training's `runner/studios_config.py` and Blog's copy with this, each studio using its own product name:

  ```python
  """The studios config, kept in the core (studio_core.studios_config); this module names the
  studio in what it says, and is kept so every existing import still works."""
  from studio_core import studios_config as _shared
  from studio_core.studios_config import *  # noqa: F401,F403
  from studio_core.studios_config import _locked, _update  # noqa: F401  used by tests

  _shared.PRODUCT = 'Presentation Studio'
  ```

  Then run:

  ```bash
  grep -rn "studios_config\._" studios/*/tests | head
  ```

  For each private name a test uses, add it to the `from studio_core.studios_config import ...` line above.
- [ ] **Step 6: Run everything:**

  ```bash
  bash scripts/ci/check_all.sh python3
  ```

  Expected: all parts pass, and core now runs 3 + N tests.
- [ ] **Step 7: Delete Presentation's `tests/test_studios_config.py`** (now in the core), and remove its `vendor.json` entries for `studios_config.py` and `test_studios_config.py`. Run `bash scripts/ci/check_all.sh python3 presentation` again. Expected: pass.
- [ ] **Step 8: Commit:**

  ```bash
  git add -A core studios && git commit -m "Keep the studios config in the core, with a folder for work on this computer"
  ```

### Task 3.3: `server` in the core

**Files:**
- Create: `core/studio_core/server.py` (from `studios/presentation/skills/presentation-studio/scripts/server.py`)
- Create: `core/tests/test_server.py` (from `studios/presentation/tests/test_server_security.py`)
- Modify: `studios/presentation/skills/presentation-studio/scripts/server.py`, which becomes the Presentation subclass and re-export

- [ ] **Step 1: Copy:**

  ```bash
  cp studios/presentation/skills/presentation-studio/scripts/server.py core/studio_core/server.py && cp studios/presentation/tests/test_server_security.py core/tests/test_server.py
  ```

- [ ] **Step 2: Make the core server name nothing.** In `core/studio_core/server.py`, make these edits.
  - **Imports:** replace `import computer` and `from workspace import WorkspaceError` with `from studio_core.errors import WorkspaceError`.
  - **Module constants:** delete `TOKEN_HEADER`, `PAGE_DIR`, `PAGE`, `COMPUTER_CACHE`, `READS` and `WRITES`. Add:

    ```python
    READS: tuple = ()
    WRITES: tuple = ()
    ```

  - **`Handler.version_string`:** return `self.server.desk.page.product`.
  - **`Handler.respond`:** catch `WorkspaceError` as now. This is the core's class, which every studio's now is too.
  - **`Page`:** replace its class header and `__init__` with:

    ```python
    class Page:
        """What the page may ask for and what it is refused. It holds the key; it has no socket.

        A program that serves a page makes a subclass. It names itself (`product`), its key's
        header (`token_header`), the folder of its own files (`page_dir`) and which of them are
        served at which address (`files`, {path: (name, content type)}). It adds addresses to
        `reads` and `writes` and answers them in `read` and `write`. Every rule about who may ask
        stays here, in `answer` and `change`.
        """
        product = 'Studio'
        token_header = 'X-Studio-Token'
        page_dir: Path | None = None
        files: dict = {}
        reads, writes = READS, WRITES

        def __init__(self, port: int, token: str | None = None):
            self.token = token or secrets.token_urlsafe(32)
            self.port = port
            self.hosts = {f'{name}:{port}' for name in (HOST, 'localhost')}
    ```

  - **Delete** `Page.uses_google` and `Page.computer`.
  - **In `Page.answer`:**
    - Replace `if url.path in PAGE:` and the lines under it with:

      ```python
      if url.path in self.files and self.page_dir is not None:
          name, kind = self.files[url.path]
          try:
              return HTTPStatus.OK, kind, (self.page_dir / name).read_bytes()
          except OSError:
              raise Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')
      ```

    - Replace the base `read` with:

      ```python
      def read(self, path: str, one) -> tuple:
          raise Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')
      ```

  - **`Page.check_token`:** use `headers.get(self.token_header, '')`.
  - **Base `write`:** replace with:

    ```python
    def write(self, path: str, sent: dict) -> tuple:
        raise Refusal(HTTPStatus.NOT_FOUND, 'Nothing is served here.')
    ```

  - **`Desk.__init__`:** accept `token: str | None = None` and pass it on with `self.page = page(self.port, token=token) if token else page(self.port)`.
  - **Module docstring:** update it to say the header, files and folder come from the subclass.

  Then check what Presentation's `page.Studio` passes for the key:

  ```bash
  grep -n "token" studios/presentation/runner/page.py | head
  ```

  If `page.Studio(engine, port, token=…)` builds its own `Desk`-like object, keep its signature and make sure it reaches `Page.__init__(port, token)`.
- [ ] **Step 3: Make Presentation's `server.py` the subclass.** Replace the file's body with:

  ```python
  """Presentation Studio's page server: the core's rules (studio_core.server), with this studio's
  name, key header, files and its look at this computer. Kept so every existing import works."""
  from __future__ import annotations

  import threading
  import time
  from http import HTTPStatus
  from pathlib import Path

  import computer
  from studio_core import server as _core
  from studio_core.server import *  # noqa: F401,F403
  from studio_core.server import Desk as _Desk

  TOKEN_HEADER = 'X-Presentation-Studio-Token'
  PAGE_DIR = Path(__file__).resolve().parent / 'desk'
  PAGE = {
      # <move the PAGE dict from the core copy here, unchanged>
  }
  COMPUTER_CACHE = 60
  READS = ('/api/computer',)
  WRITES = ('/api/computer',)


  class Page(_core.Page):
      product = 'PresentationStudio'
      token_header = TOKEN_HEADER
      page_dir = PAGE_DIR
      files = PAGE
      reads, writes = READS, WRITES

      def __init__(self, port: int, token: str | None = None):
          super().__init__(port, token)
          self._looking = threading.Lock()
          self._looked: tuple[float, dict] | None = None

      def uses_google(self) -> bool:
          """A deck is made in Google Slides unless chosen otherwise."""
          return True

      def computer(self, look: bool) -> dict | None:
          if look:
              with self._looking:
                  seen = self._looked
                  if not seen or time.monotonic() - seen[0] >= COMPUTER_CACHE:
                      self._looked = (time.monotonic(), computer.check(google=self.uses_google()))
          return self._looked[1] if self._looked else None

      def read(self, path: str, one) -> tuple:
          return as_json(HTTPStatus.OK, {'computer': self.computer(look=False)})

      def write(self, path: str, sent: dict) -> tuple:
          return as_json(HTTPStatus.OK, {'computer': self.computer(look=True)})


  class Desk(_Desk):
      def __init__(self, port: int = 0, page=Page, token: str | None = None):
          super().__init__(port, page=page, token=token)
  ```

  The `PAGE` dict is moved unchanged from lines 52–59 of the original file.
- [ ] **Step 4: Point the core test at a small page of its own.**
  - In `core/tests/test_server.py`, change the imports to `from studio_core import server`.
  - Where the tests built `server.Desk(0)`, define a test-only subclass at the top of the file and use it:

    ```python
    import tempfile
    from pathlib import Path

    FOLDER = tempfile.mkdtemp()
    (Path(FOLDER) / 'index.html').write_text('<!doctype html><title>t</title>', encoding='utf-8')


    class TestPage(server.Page):
        product = 'TestStudio'
        token_header = 'X-Test-Token'
        page_dir = Path(FOLDER)
        files = {'/': ('index.html', 'text/html; charset=utf-8')}
        reads = writes = ('/api/echo',)

        def read(self, path, one):
            return server.as_json(200, {'ok': True})

        def write(self, path, sent):
            return server.as_json(200, {'sent': sent})
    ```

  - Replace the header name the tests send with `TestPage.token_header`, and `/api/computer` with `/api/echo`.
  - Remove any test that only checked the computer look; Presentation's own tests keep that.
- [ ] **Step 5: Run:**

  ```bash
  bash scripts/ci/check_all.sh python3 core presentation
  ```

  - Expected: pass.
  - Then delete `studios/presentation/tests/test_server_security.py` only if every case it had is now in `core/tests/test_server.py`. Keep any case that uses Presentation's real page.
- [ ] **Step 6: Update `vendor.json`.** Remove the `server.py` and `test_server_security.py` entries. Run Presentation's checks again. Expected: pass.
- [ ] **Step 7: Commit:**

  ```bash
  git add -A core studios && git commit -m "Keep the page server's rules in the core; Presentation names its own page"
  ```

### Task 3.4: `computer` and `choices` in the core

**Files:**
- Create: `core/studio_core/computer.py` (from Presentation's `computer.py`, standard library only)
- Create: `core/studio_core/choices.py`
- Create: `core/tests/test_choices.py`
- Modify: Presentation's and Training's `computer.py` (become re-exports)

- [ ] **Step 1: Write the failing test** in `core/tests/test_choices.py`:

  ```python
  import unittest

  from studio_core import choices
  from studio_core.errors import WorkspaceError


  class ChoicesTests(unittest.TestCase):
      def test_accepts_what_every_studio_accepts(self):
          checked = choices.check({'assistant': {'agent': 'claude', 'model': 'opus', 'effort': 'high'},
                                   'output': 'pptx', 'share': 'asked',
                                   'brand': {'brand': 'acme', 'variant': 'light', 'release': 'v1.4.0'},
                                   'person': {'name': 'A Writer'}, 'local': {'root': '~/Studios'}})
          self.assertEqual(checked['output'], 'pptx')

      def test_refuses_an_effort_the_agent_does_not_take(self):
          with self.assertRaisesRegex(WorkspaceError, 'reasoning level'):
              choices.check({'assistant': {'agent': 'claude', 'effort': 'ultra'}})

      def test_refuses_unknown_values_and_keys(self):
          for changes in ({'output': 'pdf'}, {'share': 'never'}, {'brand': {'brand': 'has space'}},
                          {'assistant': {'agent': 'gpt'}}, {'colour': 'red'},
                          {'person': {'name': 'x' * 101}}, {'local': {'root': ''}}):
              with self.subTest(changes=changes), self.assertRaises(WorkspaceError):
                  choices.check(changes)

      def test_null_clears_a_value(self):
          self.assertEqual(choices.check({'brand': {'release': None}}), {'brand': {'release': None}})


  if __name__ == '__main__':
      unittest.main()
  ```

- [ ] **Step 2: Run it.**

  ```bash
  cd core && python3 -m unittest tests.test_choices -v
  ```

  Expected: FAIL, `cannot import name 'choices'`.
- [ ] **Step 3: Write `core/studio_core/choices.py`.** The values are copied from `studios/presentation/runner/settings.py` (lines 74–90 at import).

  ```python
  """What a shared value may be: the same answer in every studio and on the home page.

  What a caller needs to know
  ---------------------------
      changes = choices.check({'assistant': {'agent': 'claude', 'effort': 'high'}})

  - `check` returns the changes as given when every value is one the studios accept, and
    raises WorkspaceError with one sentence otherwise. `None` clears a value. Keys the studios
    config does not share are refused. Repository addresses are checked by studios_config
    itself, which refuses one carrying a password or token.
  """
  from __future__ import annotations

  import re

  from studio_core.errors import WorkspaceError

  AGENTS = ('claude', 'codex')
  LEVELS = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')
  EFFORTS = {'claude': ('low', 'medium', 'high', 'xhigh', 'max'), 'codex': LEVELS}
  OUTPUTS = ('google', 'pptx')
  SHARES = ('decision', 'asked')
  WORD = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
  RELEASE = re.compile(r'^[\w][\w.+-]{0,99}$')
  NAME, MODEL, ADDRESS, FOLDER = 100, 100, 2000, 1000

  MEMBERS = {
      'team': ('repository', 'branch'), 'person': ('name',),
      'assistant': ('agent', 'model', 'effort'),
      'brand': ('repository', 'release', 'brand', 'variant'), 'local': ('root',),
  }
  WORDS = ('output', 'share')


  def _text(value, most: int, what: str) -> None:
      if not isinstance(value, str) or not value.strip() or len(value) > most:
          raise WorkspaceError(f'{what} is between 1 and {most:,} characters.')


  def check(changes: dict) -> dict:
      if not isinstance(changes, dict):
          raise WorkspaceError('Give the shared values as the studios config names them.')
      for key, value in changes.items():
          if key in WORDS:
              allowed = OUTPUTS if key == 'output' else SHARES
              if value is not None and value not in allowed:
                  raise WorkspaceError(f'"{key}" is one of: ' + ', '.join(allowed) + '.')
              continue
          if key not in MEMBERS or not isinstance(value, dict):
              raise WorkspaceError(f'"{key}" is not a value the studios share.')
          for member, given in value.items():
              if member not in MEMBERS[key]:
                  raise WorkspaceError(f'"{key}.{member}" is not a value the studios share.')
              if given is not None:
                  _member(key, member, given, value)
      return changes


  def _member(key: str, member: str, given, group: dict) -> None:
      if (key, member) == ('assistant', 'agent'):
          if given not in AGENTS:
              raise WorkspaceError('The agent is one of: ' + ', '.join(AGENTS) + '.')
      elif (key, member) == ('assistant', 'effort'):
          levels = EFFORTS.get(group.get('agent'), LEVELS)
          if given not in levels:
              raise WorkspaceError('The reasoning level is one of: ' + ', '.join(levels) + '.')
      elif (key, member) == ('assistant', 'model'):
          _text(given, MODEL, "The model's name")
      elif (key, member) == ('person', 'name'):
          _text(given, NAME, 'Your name')
      elif member in ('brand', 'variant'):
          if not isinstance(given, str) or not WORD.match(given):
              raise WorkspaceError(f'A {member} is letters, digits, dots, dashes or underscores.')
      elif member == 'release':
          if not isinstance(given, str) or not RELEASE.match(given):
              raise WorkspaceError('A release is a tag name, such as v1.4.0.')
      elif member == 'repository':
          _text(given, ADDRESS, "A repository's address")
      elif member == 'branch':
          _text(given, 200, 'A branch')
      elif member == 'root':
          _text(given, FOLDER, 'A folder')
  ```

- [ ] **Step 4: Run it.** Use the same command as Step 2. Expected: 4 tests, OK.
- [ ] **Step 5: Move `computer.py`.**

  ```bash
  cp studios/presentation/skills/presentation-studio/scripts/computer.py core/studio_core/computer.py
  ```

  - In the core copy, replace each product-name literal in a message with the module-level `PRODUCT = 'This studio'`, the same way as Task 3.2 Step 3.
  - Replace Presentation's and Training's `computer.py` with a re-export:

    ```python
    """This computer's look, kept in the core (studio_core.computer)."""
    from studio_core import computer as _shared
    from studio_core.computer import *  # noqa: F401,F403

    _shared.PRODUCT = 'Presentation Studio'   # 'Training Studio' in Training's copy
    ```

  - Run this to find private names tests use, and add them to the import:

    ```bash
    grep -rn "computer\._" studios/*/tests | head
    ```

  Blog keeps its own `computer.py`; Task 7.6 decides whether it can share this one.
- [ ] **Step 6: Run:**

  ```bash
  bash scripts/ci/check_all.sh python3 core training presentation
  ```

  Expected: pass.
- [ ] **Step 7: Commit:**

  ```bash
  git add -A core studios && git commit -m "Share the look at this computer and the allowed shared values"
  ```

### Task 3.5: One copy of the identical page files

**Files:**
- Create: `ui-kit/style.css`, `ui-kit/markdown.js` (moved from Training)
- Replace with symlinks: the three studios' `style.css` and `markdown.js`
- Delete: `studios/blog/training-studio-ui.json` (the vendoring record for those two files)

- [ ] **Step 1: Confirm they are still identical.** Run:

  ```bash
  for f in style.css markdown.js; do shasum studios/training/skills/training-studio/scripts/desk/$f studios/presentation/skills/presentation-studio/scripts/desk/$f studios/blog/skills/blog-studio/assets/management/$f; done
  ```

  Expected: three equal hashes per file. If one differs, stop and show the user the diff.
- [ ] **Step 2: Move and link:**

  ```bash
  mkdir -p ui-kit && git mv studios/training/skills/training-studio/scripts/desk/style.css ui-kit/style.css && git mv studios/training/skills/training-studio/scripts/desk/markdown.js ui-kit/markdown.js && for f in style.css markdown.js; do ln -s ../../../../../../ui-kit/$f studios/training/skills/training-studio/scripts/desk/$f; ln -sf ../../../../../../ui-kit/$f studios/presentation/skills/presentation-studio/scripts/desk/$f; ln -sf ../../../../../../ui-kit/$f studios/blog/skills/blog-studio/assets/management/$f; done
  ```

- [ ] **Step 3: Find and delete the vendoring record.** Run:

  ```bash
  git ls-files studios/blog | grep -i 'training-studio-ui'
  ```

  `git rm` the file it prints. Remove the `style.css` and `markdown.js` entries from Presentation's `vendor.json`.
- [ ] **Step 4: Run everything.**

  ```bash
  bash scripts/ci/check_all.sh python3
  ```

  - Expected: pass.
  - A page-file server reading through `Path.read_bytes()` follows links, so the pages are unchanged.
  - If a package check refuses the links, extend it to accept links resolving inside `ui-kit/`, with a test, as in Task 3.1 Step 6.
- [ ] **Step 5: Commit:**

  ```bash
  git add -A ui-kit studios && git commit -m "Keep one copy of the page's style and Markdown reader"
  ```

---

## Phase 4: The home page

### Task 4.1: The catalog of studios

**Files:**
- Create: `home/scripts/catalog.py`
- Create: `home/scripts/studio_core` (symlink to `../../core/studio_core`)
- Create: `home/tests/__init__.py`, `home/tests/test_catalog.py`

- [ ] **Step 1: Link the core.**

  ```bash
  mkdir -p home/scripts home/tests home/page && ln -s ../../core/studio_core home/scripts/studio_core && touch home/tests/__init__.py
  ```

- [ ] **Step 2: Write the failing test** in `home/tests/test_catalog.py`:

  ```python
  import sys
  import tempfile
  import unittest
  from pathlib import Path

  sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
  import catalog  # noqa: E402


  class CatalogTests(unittest.TestCase):
      def test_three_studios_in_a_checkout(self):
          found = {studio.id: studio for studio in catalog.studios()}
          self.assertEqual(sorted(found), ['blog', 'presentation', 'training'])
          self.assertEqual(found['training'].root, catalog.REPO / 'studios' / 'training')
          self.assertTrue(found['training'].installed)

      def test_links_carry_the_key_the_way_each_studio_reads_it(self):
          found = {studio.id: studio for studio in catalog.studios()}
          self.assertEqual(found['training'].link('http://127.0.0.1:5/', 'K'),
                           'http://127.0.0.1:5/#token=K')
          self.assertEqual(found['blog'].link('http://127.0.0.1:6/#old', 'K'),
                           'http://127.0.0.1:6/#K')

      def test_command_runs_the_studios_own_entry(self):
          studio = catalog.Studio('x', 'X Studio', Path('/r'), ('runner/studio.py', 'serve'), 'token={}')
          self.assertEqual(studio.command('/py'), ['/py', '/r/runner/studio.py', 'serve'])

      def test_a_missing_root_is_not_installed(self):
          with tempfile.TemporaryDirectory() as folder:
              studio = catalog.Studio('x', 'X', Path(folder) / 'none', ('a.py',), '{}')
              self.assertFalse(studio.installed)


  if __name__ == '__main__':
      unittest.main()
  ```

- [ ] **Step 3: Run it.**

  ```bash
  cd home && python3 -m unittest tests.test_catalog -v
  ```

  Expected: FAIL, `No module named 'catalog'`.
- [ ] **Step 4: Write `home/scripts/catalog.py`:**

  ```python
  """The studios Marketing Studio knows: where each one is, and how to open it with a key.

  What a caller needs to know
  ---------------------------
      for studio in catalog.studios():
          studio.id, studio.name, studio.root, studio.installed
          studio.command(python)          # its own command, which serves its page
          studio.link(address, key)       # the link for the person, with the key in it

  - A studio is opened by running its own command with HANDOFF set to
    {"token": <key>, "home": <the home page's link>}. It serves with that key, prints one JSON
    line naming its address (never the key), and opens no browser itself.
  - `root` is studios/<id> in a checkout of the repository, and <id>-studio beside home/ in an
    installed version. A studio whose entry is missing is not installed.
  """
  from __future__ import annotations

  from dataclasses import dataclass
  from pathlib import Path

  HANDOFF = 'MARKETING_STUDIO_HANDOFF'
  REPO = Path(__file__).resolve().parents[2]   # the checkout, or the installed version


  @dataclass(frozen=True)
  class Studio:
      id: str
      name: str
      root: Path
      entry: tuple          # the script, from root, and its arguments
      fragment: str         # how the key rides in the link: 'token={}' or '{}'

      @property
      def installed(self) -> bool:
          return (self.root / self.entry[0]).is_file()

      def command(self, python: str) -> list[str]:
          return [python, str(self.root / self.entry[0]), *self.entry[1:]]

      def link(self, address: str, key: str) -> str:
          return address.split('#', 1)[0].rstrip('/') + '/#' + self.fragment.format(key)


  ENTRIES = (
      ('training', 'Training Studio', 'training-studio', ('runner/studio.py', 'serve'), 'token={}'),
      ('presentation', 'Presentation Studio', 'presentation-studio',
       ('runner/studio.py', 'serve'), 'token={}'),
      ('blog', 'Blog Studio', 'blog-studio',
       ('skills/blog-studio/scripts/start_studio.py', 'open', '--no-open', '--json'), '{}'),
  )


  def studios() -> list[Studio]:
      """Every studio Marketing Studio knows, where this copy of it keeps them."""
      checkout = (REPO / 'studios').is_dir()
      return [Studio(id, name, REPO / 'studios' / id if checkout else REPO / folder, entry, fragment)
              for id, name, folder, entry, fragment in ENTRIES]
  ```

- [ ] **Step 5: Run it.** Use the same command as Step 3. Expected: 4 tests, OK.
- [ ] **Step 6: Commit:**

  ```bash
  git add -A home && git commit -m "Name the studios the home page opens, and how"
  ```

### Task 4.2: The launcher

**Files:**
- Create: `home/scripts/launcher.py`
- Create: `home/tests/fake_studio.py`, `home/tests/test_launcher.py`

- [ ] **Step 1: Write the fake studio** in `home/tests/fake_studio.py`:

  ```python
  """A stand-in studio for the launcher's tests. FAKE_STUDIO says what it does:
  address | url | error | silent | exit | elsewhere. It writes the key it was handed to
  FAKE_STUDIO_SAW, when that is set."""
  import json
  import os
  import sys
  import time

  handed = json.loads(os.environ.pop('MARKETING_STUDIO_HANDOFF', '{}'))
  if os.environ.get('FAKE_STUDIO_SAW'):
      with open(os.environ['FAKE_STUDIO_SAW'], 'w', encoding='utf-8') as out:
          json.dump(handed, out)
  mode = os.environ.get('FAKE_STUDIO', 'address')
  if mode == 'address':
      print(json.dumps({'address': 'http://127.0.0.1:4321/', 'opened': False}), flush=True)
  elif mode == 'url':
      print(json.dumps({'url': 'http://127.0.0.1:4322/#stripped'}), flush=True)
  elif mode == 'error':
      print(json.dumps({'error': 'A runner is already serving on this computer (process 9).'}), flush=True)
      sys.exit(2)
  elif mode == 'elsewhere':
      print(json.dumps({'address': 'http://example.com/'}), flush=True)
  elif mode == 'exit':
      print('Traceback: it broke', file=sys.stderr, flush=True)
      sys.exit(1)
  time.sleep(600)
  ```

- [ ] **Step 2: Write the failing tests** in `home/tests/test_launcher.py`:

  ```python
  import json
  import os
  import sys
  import tempfile
  import unittest
  from pathlib import Path

  HERE = Path(__file__).resolve().parent
  sys.path.insert(0, str(HERE.parent / 'scripts'))
  import catalog  # noqa: E402
  import launcher  # noqa: E402
  from studio_core.errors import WorkspaceError  # noqa: E402

  FAKE = catalog.Studio('fake', 'Fake Studio', HERE, ('fake_studio.py',), 'token={}')


  class LauncherTests(unittest.TestCase):
      def setUp(self):
          self.folder = tempfile.TemporaryDirectory()
          self.saw = Path(self.folder.name) / 'saw.json'
          os.environ['FAKE_STUDIO_SAW'] = str(self.saw)
          self.opener = launcher.Launcher([FAKE], 'http://127.0.0.1:9/#token=H',
                                          logs=Path(self.folder.name) / 'logs', wait=10)

      def tearDown(self):
          self.opener.stop()
          for name in ('FAKE_STUDIO', 'FAKE_STUDIO_SAW'):
              os.environ.pop(name, None)
          self.folder.cleanup()

      def test_hands_over_a_key_and_returns_the_link(self):
          link = self.opener.open('fake')
          saw = json.loads(self.saw.read_text())
          self.assertEqual(link, f'http://127.0.0.1:4321/#token={saw["token"]}')
          self.assertEqual(saw['home'], 'http://127.0.0.1:9/#token=H')
          self.assertGreaterEqual(len(saw['token']), 32)
          self.assertEqual(self.opener.running(), {'fake': True})

      def test_a_second_open_reuses_the_running_studio(self):
          self.assertEqual(self.opener.open('fake'), self.opener.open('fake'))

      def test_a_url_without_a_key_is_read_as_the_address(self):
          os.environ['FAKE_STUDIO'] = 'url'
          self.assertTrue(self.opener.open('fake').startswith('http://127.0.0.1:4322/#token='))

      def test_the_studios_own_refusal_is_what_the_person_reads(self):
          os.environ['FAKE_STUDIO'] = 'error'
          with self.assertRaisesRegex(WorkspaceError, 'already serving'):
              self.opener.open('fake')
          self.assertEqual(self.opener.running(), {'fake': False})

      def test_an_address_elsewhere_is_refused(self):
          os.environ['FAKE_STUDIO'] = 'elsewhere'
          with self.assertRaisesRegex(WorkspaceError, 'did not open'):
              self.opener.open('fake')

      def test_a_studio_that_exits_shows_its_log(self):
          os.environ['FAKE_STUDIO'] = 'exit'
          with self.assertRaisesRegex(WorkspaceError, 'it broke'):
              self.opener.open('fake')

      def test_a_silent_studio_is_ended(self):
          os.environ['FAKE_STUDIO'] = 'silent'
          self.opener.wait = 0.5
          with self.assertRaisesRegex(WorkspaceError, 'did not open'):
              self.opener.open('fake')
          self.assertEqual(self.opener.running(), {'fake': False})

      def test_stop_ends_every_studio(self):
          self.opener.open('fake')
          self.opener.stop()
          self.assertEqual(self.opener.running(), {'fake': False})

      def test_unknown_and_missing_studios_are_refused(self):
          with self.assertRaisesRegex(WorkspaceError, 'no studio'):
              self.opener.open('nope')
          missing = catalog.Studio('gone', 'Gone Studio', HERE / 'absent', ('x.py',), '{}')
          opener = launcher.Launcher([missing], 'h', logs=Path(self.folder.name))
          with self.assertRaisesRegex(WorkspaceError, 'not installed'):
              opener.open('gone')


  if __name__ == '__main__':
      unittest.main()
  ```

- [ ] **Step 3: Run them.**

  ```bash
  cd home && python3 -m unittest tests.test_launcher -v
  ```

  Expected: FAIL, `No module named 'launcher'`.
- [ ] **Step 4: Write `home/scripts/launcher.py`:**

  ```python
  """Opening a studio for the person: started once, handed a key, and stopped with the home page.

  What a caller needs to know
  ---------------------------
      opener = launcher.Launcher(catalog.studios(), home_link, logs=folder)
      link = opener.open('training')     # the studio's link with its key; started if need be
      opener.running()                   # {'training': True, ...}
      opener.stop()                      # every studio this started

  - A studio is started with HANDOFF set to {"token", "home"}, and the first line it prints is
    read within `wait` seconds. {"error": ...} is raised as WorkspaceError with that sentence,
    which is how a studio already serving from its own window is reported. Otherwise the line
    names the address as "address" or "url", whose fragment is dropped. It must be on
    127.0.0.1. What it writes to stderr goes to <logs>/<id>.log, whose last lines are shown
    when it fails.
  - The key is never logged, printed or written to disk here.
  - `stop` sends SIGTERM to each studio still running and waits for it, then kills it.
  """
  from __future__ import annotations

  import json
  import os
  import queue
  import secrets
  import signal
  import subprocess
  import sys
  import threading
  from pathlib import Path

  from catalog import HANDOFF, Studio
  from studio_core.errors import WorkspaceError

  WAIT = 60.0     # seconds a studio has to say where it is; it may fetch a workspace first
  TAIL = 12       # lines of a studio's log shown when it fails
  LOCAL = 'http://127.0.0.1:'


  class Launcher:
      def __init__(self, studios: list[Studio], home: str, logs: Path,
                   python: str = sys.executable, wait: float = WAIT):
          self.studios = {studio.id: studio for studio in studios}
          self.home, self.logs, self.python, self.wait = home, logs, python, wait
          self._open: dict[str, tuple[subprocess.Popen, str]] = {}
          self._lock = threading.Lock()
          self._starting = {id: threading.Lock() for id in self.studios}

      def running(self) -> dict[str, bool]:
          with self._lock:
              return {id: id in self._open and self._open[id][0].poll() is None
                      for id in self.studios}

      def open(self, id: str) -> str:
          studio = self.studios.get(id)
          if studio is None:
              raise WorkspaceError('There is no studio of that name.')
          if not studio.installed:
              raise WorkspaceError(f'{studio.name} is not installed.')
          with self._starting[id]:
              with self._lock:
                  kept = self._open.get(id)
              if kept and kept[0].poll() is None:
                  return kept[1]
              process, link = self._start(studio)
              with self._lock:
                  self._open[id] = (process, link)
              return link

      def stop(self) -> None:
          with self._lock:
              started, self._open = [process for process, _ in self._open.values()], {}
          for process in started:
              end(process)

      def _start(self, studio: Studio) -> tuple[subprocess.Popen, str]:
          key = secrets.token_urlsafe(32)
          env = {**os.environ, HANDOFF: json.dumps({'token': key, 'home': self.home})}
          self.logs.mkdir(parents=True, exist_ok=True)
          log = self.logs / f'{studio.id}.log'
          with log.open('w', encoding='utf-8') as errors:
              process = subprocess.Popen(studio.command(self.python), cwd=studio.root, env=env,
                                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                         stderr=errors, text=True)
          line = first_line(process, self.wait)
          said = None
          try:
              said = json.loads(line) if line else None
          except ValueError:
              pass
          if isinstance(said, dict) and said.get('error'):
              end(process)
              raise WorkspaceError(str(said['error']))
          address = (said.get('address') or said.get('url')) if isinstance(said, dict) else None
          if not isinstance(address, str) or not address.startswith(LOCAL):
              end(process)
              raise WorkspaceError(f'{studio.name} did not open.{tail(log)}')
          return process, studio.link(address, key)


  def first_line(process: subprocess.Popen, wait: float) -> str | None:
      """The first line the studio prints, or None when it says nothing in time or ends.
      What it prints later is read and dropped, so it never blocks on a full pipe."""
      lines: queue.Queue = queue.Queue()

      def read():
          with process.stdout:          # closed here once the studio has ended
              for number, line in enumerate(process.stdout):
                  if number == 0:
                      lines.put(line.strip())
          lines.put(None)

      threading.Thread(target=read, daemon=True).start()
      try:
          return lines.get(timeout=wait)
      except queue.Empty:
          return None


  def tail(log: Path) -> str:
      try:
          kept = log.read_text(encoding='utf-8', errors='replace').strip().splitlines()[-TAIL:]
      except OSError:
          return ''
      return ('\n' + '\n'.join(kept)) if kept else ''


  def end(process: subprocess.Popen, grace: float = 10.0) -> None:
      if process.poll() is None:
          process.send_signal(signal.SIGTERM)
          try:
              process.wait(grace)
          except subprocess.TimeoutExpired:
              process.kill()
              process.wait()
  ```

- [ ] **Step 5: Run the tests.** Use the same command as Step 3. Expected: 9 tests, OK.
- [ ] **Step 6: Commit:**

  ```bash
  git add -A home && git commit -m "Open a studio with a key of its own, and stop it with the home page"
  ```

### Task 4.3: The home server

**Files:**
- Create: `home/scripts/page.py`
- Create: `home/tests/test_page.py`

- [ ] **Step 1: Write the failing tests** in `home/tests/test_page.py`:

  ```python
  import http.client
  import json
  import os
  import sys
  import tempfile
  import unittest
  from pathlib import Path

  HERE = Path(__file__).resolve().parent
  sys.path.insert(0, str(HERE.parent / 'scripts'))
  import catalog  # noqa: E402
  import page  # noqa: E402
  from studio_core import server, studios_config  # noqa: E402

  FAKE = catalog.Studio('fake', 'Fake Studio', HERE, ('fake_studio.py',), 'token={}')


  class HomePageTests(unittest.TestCase):
      def setUp(self):
          self.folder = tempfile.TemporaryDirectory()
          os.environ['STUDIOS_CONFIG'] = str(Path(self.folder.name) / 'studios-config.json')
          os.environ['MARKETING_STUDIO_DATA'] = str(Path(self.folder.name) / 'data')
          os.environ.pop('FAKE_STUDIO', None)
          self.desk = server.Desk(0, page=page.factory([FAKE]))
          self.desk.start()

      def tearDown(self):
          self.desk.page.launcher.stop()
          self.desk.stop()
          for name in ('STUDIOS_CONFIG', 'MARKETING_STUDIO_DATA'):
              os.environ.pop(name, None)
          self.folder.cleanup()

      def call(self, method, path, body=None, key=True, origin=True, host=None):
          connection = http.client.HTTPConnection('127.0.0.1', self.desk.port, timeout=30)
          headers = {'Host': host or f'127.0.0.1:{self.desk.port}'}
          if key:
              headers[page.HomePage.token_header] = self.desk.token
          data = None
          if body is not None:
              data = json.dumps(body).encode()
              headers['Content-Type'] = 'application/json'
              if origin:
                  headers['Origin'] = f'http://127.0.0.1:{self.desk.port}'
          connection.request(method, path, body=data, headers=headers)
          answer = connection.getresponse()
          return answer.status, json.loads(answer.read() or b'null')

      def test_home_lists_studios_and_set_up(self):
          status, home = self.call('GET', '/api/home')
          self.assertEqual(status, 200)
          self.assertEqual(home['studios'], [{'id': 'fake', 'name': 'Fake Studio',
                                              'installed': True, 'running': False}])
          self.assertEqual(home['setup'], {'enabled': ['fake'], 'done': False})
          self.assertEqual(home['shared'], {})

      def test_shared_values_are_saved_in_the_studios_config(self):
          status, saved = self.call('POST', '/api/shared', {
              'changes': {'assistant': {'agent': 'codex', 'effort': 'ultra'}}, 'seen': {}})
          self.assertEqual(status, 200, saved)
          found, _ = studios_config.read()
          self.assertEqual(found['assistant'], {'agent': 'codex', 'effort': 'ultra'})

      def test_a_value_changed_elsewhere_is_not_written_over(self):
          studios_config.update({'share': 'asked'})
          status, refused = self.call('POST', '/api/shared',
                                      {'changes': {'share': 'decision'}, 'seen': {}})
          self.assertEqual(status, 409)
          self.assertIn('another studio', refused['error'])

      def test_a_value_no_studio_accepts_is_refused(self):
          status, refused = self.call('POST', '/api/shared', {'changes': {'output': 'pdf'}, 'seen': {}})
          self.assertEqual(status, 409)
          self.assertIn('google, pptx', refused['error'])

      def test_set_up_is_remembered(self):
          self.call('POST', '/api/setup', {'enabled': ['fake'], 'done': True})
          _, home = self.call('GET', '/api/home')
          self.assertEqual(home['setup'], {'enabled': ['fake'], 'done': True})

      def test_open_answers_the_studios_link(self):
          status, opened = self.call('POST', '/api/open', {'studio': 'fake'})
          self.assertEqual(status, 200, opened)
          self.assertTrue(opened['link'].startswith('http://127.0.0.1:4321/#token='))
          _, home = self.call('GET', '/api/home')
          self.assertTrue(home['studios'][0]['running'])

      def test_the_rules_hold(self):
          self.assertEqual(self.call('GET', '/api/home', key=False)[0], 403)
          self.assertEqual(self.call('GET', '/api/home', host='evil.example')[0], 403)
          self.assertEqual(self.call('POST', '/api/open', {'studio': 'fake'}, origin=False)[0], 403)

      def test_the_page_is_served(self):
          connection = http.client.HTTPConnection('127.0.0.1', self.desk.port)
          connection.request('GET', '/', headers={'Host': f'127.0.0.1:{self.desk.port}'})
          answer = connection.getresponse()
          self.assertEqual(answer.status, 200)
          self.assertIn(b'Marketing Studio', answer.read())


  if __name__ == '__main__':
      unittest.main()
  ```

- [ ] **Step 2: Run them.**

  ```bash
  cd home && python3 -m unittest tests.test_page -v
  ```

  Expected: FAIL, `No module named 'page'`.
- [ ] **Step 3: Write `home/scripts/page.py`:**

  ```python
  """The home page's addresses, over the core server's rules (studio_core.server).

  What a caller needs to know
  ---------------------------
      desk = server.Desk(0, page=page.factory(catalog.studios()))

      GET  /api/home       studios, shared values, set-up, and the last look at this computer
      POST /api/computer   {}: a new look at this computer
      POST /api/shared     {"changes": {...}, "seen": {...}}: save shared values
      POST /api/setup      {"enabled": [...]} and/or {"done": true}
      POST /api/open       {"studio": id}: {"link"}, the studio started if need be

  - Shared values go to the studios config and nowhere else. A change is refused when what the
    form was shown (`seen`) differs from what the file now holds for the same value: another
    studio changed it meanwhile.
  - What only this page keeps is home.json in the data folder: ~/.local/share/marketing-studio,
    or the one MARKETING_STUDIO_DATA names.
  """
  from __future__ import annotations

  import json
  import os
  import threading
  import time
  from functools import partial
  from http import HTTPStatus
  from pathlib import Path

  from launcher import Launcher
  from studio_core import choices, computer, server, studios_config
  from studio_core.errors import WorkspaceError
  from studio_core.files import write_atomic

  PAGE_DIR = Path(__file__).resolve().parent.parent / 'page'
  COMPUTER_CACHE = 60
  STALE = ('{} was changed in another studio while this was open, so nothing was saved. '
           'Look again.')
  HTML, JS, CSS = 'text/html; charset=utf-8', 'text/javascript; charset=utf-8', 'text/css; charset=utf-8'


  def data_root() -> Path:
      return Path(os.environ.get('MARKETING_STUDIO_DATA')
                  or Path.home() / '.local' / 'share' / 'marketing-studio')


  def factory(studios):
      """What Desk calls with the port (and a key, when one was handed over)."""
      return partial(HomePage, studios=studios)


  class HomePage(server.Page):
      product = 'MarketingStudio'
      token_header = 'X-Marketing-Studio-Token'
      page_dir = PAGE_DIR
      files = {'/': ('index.html', HTML), '/app.js': ('app.js', JS),
               '/home.css': ('home.css', CSS), '/style.css': ('style.css', CSS)}
      reads = ('/api/home',)
      writes = ('/api/computer', '/api/shared', '/api/setup', '/api/open')

      def __init__(self, port: int, token: str | None = None, studios=()):
          super().__init__(port, token)
          self.studios = list(studios)
          link = f'http://{server.HOST}:{port}/#token={self.token}'
          self.launcher = Launcher(self.studios, link, logs=data_root() / 'logs')
          self._looking = threading.Lock()
          self._looked: tuple[float, dict] | None = None

      # --- reads ---------------------------------------------------------------------------

      def read(self, path: str, one) -> tuple:
          shared, problem = studios_config.read()
          running = self.launcher.running()
          return server.as_json(HTTPStatus.OK, {
              'studios': [{'id': s.id, 'name': s.name, 'installed': s.installed,
                           'running': running.get(s.id, False)} for s in self.studios],
              'shared': shared, 'shared_problem': problem, 'setup': self.setup(),
              'computer': self._looked[1] if self._looked else None})

      # --- writes --------------------------------------------------------------------------

      def write(self, path: str, sent: dict) -> tuple:
          if path == '/api/computer':
              return server.as_json(HTTPStatus.OK, {'computer': self.look()})
          if path == '/api/shared':
              changes = choices.check(sent.get('changes'))
              seen = sent.get('seen') if isinstance(sent.get('seen'), dict) else {}
              studios_config.update(changes, guard=guard(changes, seen))
              return server.as_json(HTTPStatus.OK, {'shared': studios_config.read()[0]})
          if path == '/api/setup':
              return server.as_json(HTTPStatus.OK, {'setup': self.remember(sent)})
          studio = sent.get('studio')
          if not isinstance(studio, str):
              raise WorkspaceError('Say which studio to open.')
          return server.as_json(HTTPStatus.OK, {'link': self.launcher.open(studio)})

      # --- what this page keeps ------------------------------------------------------------

      def setup(self) -> dict:
          known = [s.id for s in self.studios]
          try:
              kept = json.loads((data_root() / 'home.json').read_text(encoding='utf-8'))
          except (OSError, ValueError):
              kept = {}
          enabled = [id for id in kept.get('enabled', known) if id in known]
          return {'enabled': enabled, 'done': kept.get('done') is True}

      def remember(self, sent: dict) -> dict:
          now = self.setup()
          if 'enabled' in sent:
              known = {s.id for s in self.studios}
              given = sent['enabled']
              if not isinstance(given, list) or not given or not set(given) <= known:
                  raise WorkspaceError('Choose at least one of the studios listed.')
              now['enabled'] = [s.id for s in self.studios if s.id in given]
          if 'done' in sent:
              now['done'] = sent['done'] is True
          write_atomic(data_root() / 'home.json', json.dumps({'schema': 1, **now}, indent=2) + '\n')
          return now

      def look(self) -> dict:
          with self._looking:
              seen = self._looked
              if not seen or time.monotonic() - seen[0] >= COMPUTER_CACHE:
                  shared, _ = studios_config.read()
                  self._looked = (time.monotonic(),
                                  computer.check(google=shared.get('output', 'google') == 'google'))
              return self._looked[1]


  def guard(changes: dict, seen: dict):
      """Refuse when what the form was shown is no longer what the file holds."""
      def at(values: dict, key: str, member: str | None):
          value = values.get(key)
          return (value or {}).get(member) if member else value

      def check(now: dict) -> None:
          for key, value in changes.items():
              for member in (value if isinstance(value, dict) else {None: value}):
                  if at(now, key, member) != at(seen, key, member):
                      raise WorkspaceError(STALE.format(f'{key}.{member}' if member else key))
      return check
  ```

- [ ] **Step 4: Write a minimal page** so `test_the_page_is_served` can pass. Task 4.5 fills it in.

  `home/page/index.html`:

  ```html
  <!doctype html>
  <html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Marketing Studio</title>
    <link rel="stylesheet" href="/style.css">
    <link rel="stylesheet" href="/home.css">
    <script src="/app.js" defer></script>
  </head>
  <body>
    <header class="ms-top"><h1>Marketing Studio</h1><nav id="nav"></nav></header>
    <main id="main" aria-live="polite"><p>Opening…</p></main>
  </body>
  </html>
  ```

  Then link the shared style and create placeholders:

  ```bash
  ln -s ../../ui-kit/style.css home/page/style.css && : > home/page/app.js && : > home/page/home.css
  ```

- [ ] **Step 5: Check what `studios_config.update` hands its guard.** Run:

  ```bash
  grep -n "guard(" core/studio_core/studios_config.py
  ```

  - Expected: the guard is called with the parsed dict of what the file holds.
  - If it is called with something else, such as text, change `check(now)` above to parse it the same way the module's own `read()` does.
- [ ] **Step 6: Run the tests.** Use the same command as Step 2. Expected: 8 tests, OK.
- [ ] **Step 7: Commit:**

  ```bash
  git add -A home && git commit -m "Serve the home page: shared values, set-up and opening a studio"
  ```

### Task 4.4: The `marketing-studio` command

**Files:**
- Create: `home/scripts/marketing_studio.py`
- Create: `home/tests/test_command.py`

- [ ] **Step 1: Write the failing test** in `home/tests/test_command.py`:

  ```python
  import io
  import json
  import os
  import sys
  import tempfile
  import threading
  import time
  import unittest
  from pathlib import Path

  HERE = Path(__file__).resolve().parent
  sys.path.insert(0, str(HERE.parent / 'scripts'))
  import marketing_studio  # noqa: E402


  class Pipe(io.StringIO):
      def isatty(self):
          return False


  class CommandTests(unittest.TestCase):
      def test_serve_prints_the_address_without_its_key_and_stops(self):
          with tempfile.TemporaryDirectory() as folder:
              os.environ['MARKETING_STUDIO_DATA'] = folder
              out, opened = Pipe(), []
              stop = threading.Event()
              thread = threading.Thread(target=marketing_studio.serve,
                                        kwargs={'port': 0, 'out': out, 'opener': opened.append,
                                                'until': stop}, daemon=True)
              thread.start()
              for _ in range(50):
                  if out.getvalue():
                      break
                  time.sleep(0.1)
              said = json.loads(out.getvalue().splitlines()[0])
              stop.set()
              thread.join(10)
              os.environ.pop('MARKETING_STUDIO_DATA')
          self.assertTrue(said['address'].startswith('http://127.0.0.1:'))
          self.assertNotIn('token', json.dumps(said))
          self.assertEqual(len(opened), 1)
          self.assertIn('#token=', opened[0])

      def test_a_second_home_page_is_refused(self):
          with tempfile.TemporaryDirectory() as folder:
              os.environ['MARKETING_STUDIO_DATA'] = folder
              Path(folder, 'home.pid').write_text(f'{os.getppid()}\n', encoding='utf-8')
              try:
                  with self.assertRaisesRegex(marketing_studio.WorkspaceError, 'already open'):
                      with marketing_studio.only_one():
                          pass
              finally:
                  os.environ.pop('MARKETING_STUDIO_DATA')

      def test_a_pid_file_left_by_a_home_page_that_ended_is_taken_over(self):
          with tempfile.TemporaryDirectory() as folder:
              os.environ['MARKETING_STUDIO_DATA'] = folder
              Path(folder, 'home.pid').write_text('999999\n', encoding='utf-8')
              try:
                  with marketing_studio.only_one():
                      self.assertEqual(Path(folder, 'home.pid').read_text().strip(), str(os.getpid()))
                  self.assertFalse(Path(folder, 'home.pid').exists())
              finally:
                  os.environ.pop('MARKETING_STUDIO_DATA')


  if __name__ == '__main__':
      unittest.main()
  ```

- [ ] **Step 2: Run it.**

  ```bash
  cd home && python3 -m unittest tests.test_command -v
  ```

  Expected: FAIL, `No module named 'marketing_studio'`.
- [ ] **Step 3: Write `home/scripts/marketing_studio.py`:**

  ```python
  #!/usr/bin/env python3
  """Marketing Studio's command line.

      marketing-studio [open [training|presentation|blog]] [--port N]
          serve the home page and open it in the browser; with a studio named, open that too

  To a terminal it prints the home page's link whole, with its key, and opens it. To anything
  else it prints the address without the key and opens the page itself, so only the person
  ever holds the key. It runs until interrupted or its window is closed, and stops every
  studio it opened. One home page serves on a computer at a time (home.pid in the data folder).
  """
  import sys

  if sys.version_info < (3, 11):
      sys.exit('Marketing Studio needs Python 3.11 or newer; this is ' + sys.version.split()[0] + '.')

  import argparse
  import json
  import os
  import signal
  import threading
  from contextlib import contextmanager
  from pathlib import Path

  sys.path.insert(0, str(Path(__file__).resolve().parent))
  import catalog  # noqa: E402
  import page  # noqa: E402
  from studio_core import server  # noqa: E402
  from studio_core.errors import WorkspaceError  # noqa: E402


  def alive(pid: int) -> bool:
      try:
          os.kill(pid, 0)
      except ProcessLookupError:
          return False
      except PermissionError:
          return True
      return True


  @contextmanager
  def only_one():
      """Be the one home page on this computer, or refuse. One that ended without saying so is
      not counted."""
      path = page.data_root() / 'home.pid'
      path.parent.mkdir(parents=True, exist_ok=True)
      for _ in range(2):
          try:
              handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
          except FileExistsError:
              kept = path.read_text(encoding='utf-8').strip() if path.is_file() else ''
              if kept.isdigit() and int(kept) != os.getpid() and alive(int(kept)):
                  raise WorkspaceError(f'Marketing Studio is already open (process {kept}). Use '
                                       'its page, or close its window before opening it again.')
              path.unlink(missing_ok=True)
              continue
          os.write(handle, f'{os.getpid()}\n'.encode())
          os.close(handle)
          break
      else:
          raise WorkspaceError(f'Could not write {path}, which says Marketing Studio is open.')
      try:
          yield
      finally:
          path.unlink(missing_ok=True)


  def serve(port: int = 0, studio: str | None = None, out=None, opener=server.show,
            until: threading.Event | None = None) -> int:
      out = out or sys.stdout
      until = until or threading.Event()
      with only_one():
          desk = server.Desk(port, page=page.factory(catalog.studios()))
          shown = {'url': desk.url} if out.isatty() else {'address': desk.address}
          print(json.dumps(shown), file=out, flush=True)
          opener(desk.url)
          if studio:
              try:
                  opener(desk.page.launcher.open(studio))
              except WorkspaceError as refusal:
                  print(json.dumps({'error': str(refusal)}), file=out, flush=True)
          if threading.current_thread() is threading.main_thread():
              for stopping in (signal.SIGTERM, signal.SIGHUP):   # SIGHUP: its window was closed
                  signal.signal(stopping, lambda *_: until.set())
          desk.start()
          try:
              until.wait()
          except KeyboardInterrupt:
              pass
          finally:
              desk.page.launcher.stop()
              desk.stop()
      return 0


  def main(argv: list[str] | None = None) -> int:
      top = argparse.ArgumentParser(prog='marketing-studio', description=__doc__.splitlines()[0])
      top.add_argument('command', nargs='?', default='open', choices=('open',))
      top.add_argument('studio', nargs='?', choices=[s.id for s in catalog.studios()])
      top.add_argument('--port', type=server.port, default=0)
      args = top.parse_args(argv)
      try:
          return serve(args.port, args.studio)
      except WorkspaceError as refusal:
          print(json.dumps({'error': str(refusal)}), flush=True)
          return 2


  if __name__ == '__main__':
      sys.exit(main())
  ```

- [ ] **Step 4: Run the test.** Use the same command as Step 2. Expected: OK.
- [ ] **Step 5: Try it by hand.**

  ```bash
  python3 home/scripts/marketing_studio.py
  ```

  - Expected: one JSON line with `url`, and the browser opens a page titled "Marketing Studio".
  - Stop it with Ctrl-C.
- [ ] **Step 6: Commit:**

  ```bash
  git add -A home && git commit -m "Open Marketing Studio from one command"
  ```

### Task 4.5: The page: set-up steps and launch pad

**Files:**
- Modify: `home/page/app.js`, `home/page/home.css`
- Create: `home/tests/test_page_files.py`

- [ ] **Step 1: Write the failing test.** It checks that the page needs nothing from elsewhere and uses no `innerHTML`, which keeps CSP `default-src 'self'` and escaping safe. Put it in `home/tests/test_page_files.py`:

  ```python
  import re
  import unittest
  from pathlib import Path

  PAGE = Path(__file__).resolve().parents[1] / 'page'


  class PageFileTests(unittest.TestCase):
      def test_everything_is_served_from_here(self):
          html = (PAGE / 'index.html').read_text(encoding='utf-8')
          css = (PAGE / 'home.css').read_text(encoding='utf-8')
          js = (PAGE / 'app.js').read_text(encoding='utf-8')
          self.assertNotRegex(html, r'(src|href)="https?:')
          self.assertNotRegex(css, r'url\(\s*["\']?https?:')
          self.assertNotRegex(js, r'fetch\(\s*[`"\']https?:')

      def test_app_builds_the_page_without_innerHTML(self):
          text = (PAGE / 'app.js').read_text(encoding='utf-8')
          self.assertNotIn('innerHTML', text)
          self.assertIn("'X-Marketing-Studio-Token'", text)
          for step in ('studios', 'computer', 'you', 'work', 'brand', 'deliver'):
              self.assertRegex(text, rf"\b{step}\b", step)


  if __name__ == '__main__':
      unittest.main()
  ```

- [ ] **Step 2: Run it.**

  ```bash
  cd home && python3 -m unittest tests.test_page_files -v
  ```

  Expected: FAIL, because `app.js` is empty.
- [ ] **Step 3: Write `home/page/app.js`:**

  ```javascript
  // Marketing Studio's home page: set-up once, then the launch pad. Nothing here is fetched
  // from anywhere but this page's own server, and nothing is written as HTML.
  'use strict';

  const HEADER = 'X-Marketing-Studio-Token';
  const KEY = (() => {
    const handed = new URLSearchParams(location.hash.slice(1)).get('token');
    if (handed) {
      sessionStorage.setItem('ms-key', handed);
      history.replaceState(null, '', location.pathname);
    }
    return handed || sessionStorage.getItem('ms-key');
  })();
  window.name = 'ms-home';

  const STEPS = ['studios', 'computer', 'you', 'work', 'brand', 'deliver'];
  const EFFORTS = { claude: ['low', 'medium', 'high', 'xhigh', 'max'],
                    codex: ['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'] };
  let home = null;
  let view = { screen: 'pad', step: 0, problem: '' };

  async function call(path, body) {
    const options = { headers: { [HEADER]: KEY || '' } };
    if (body !== undefined) {
      options.method = 'POST';
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    let answer;
    try { answer = await fetch(path, options); } catch (_) {
      throw new Error('Marketing Studio is not running. Open it again from its window or Applications.');
    }
    const sent = await answer.json().catch(() => ({}));
    if (!answer.ok) throw new Error(sent.error || answer.statusText);
    return sent;
  }

  function h(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attrs)) {
      if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
      else if (value === true) node.setAttribute(name, '');
      else if (value !== false && value != null) node.setAttribute(name, value);
    }
    for (const child of children.flat()) {
      if (child != null && child !== false) node.append(child instanceof Node ? child : String(child));
    }
    return node;
  }

  const at = (key, member) => (home.shared[key] || {})[member] ?? '';
  const field = (label, input, note) => h('label', { class: 'ms-field' }, h('span', {}, label), input, note && h('small', {}, note));
  const choice = (name, value, label, checked) => h('label', { class: 'ms-choice' },
    h('input', { type: 'radio', name, value, checked }), ' ', label);
  const value = (name) => document.querySelector(`[name="${name}"]`)?.value.trim() || null;
  const picked = (name) => document.querySelector(`[name="${name}"]:checked`)?.value || null;

  async function save(changes) {
    const seen = {};
    for (const key of Object.keys(changes)) seen[key] = home.shared[key] ?? null;
    home.shared = (await call('/api/shared', { changes, seen })).shared;
  }

  // --- set-up steps: each one draws its form and saves it on Next ---------------------------

  const step = {
    studios: {
      title: 'Welcome. Which studios will you use?',
      draw: () => home.studios.map((s) => h('label', { class: 'ms-choice' },
        h('input', { type: 'checkbox', name: 'studio', value: s.id, disabled: !s.installed,
                     checked: home.setup.enabled.includes(s.id) && s.installed }),
        ' ', s.name, !s.installed && h('small', {}, ' (not installed)'))),
      save: async () => {
        const enabled = [...document.querySelectorAll('[name="studio"]:checked')].map((n) => n.value);
        home.setup = (await call('/api/setup', { enabled })).setup;
      },
    },
    computer: {
      title: 'This computer',
      draw: () => {
        const look = home.computer;
        if (!look) return [h('p', {}, 'Looking at this computer…')];
        return [h('ul', { class: 'ms-checks' }, look.items.map((item) => h('li', { class: `ms-${item.state}` },
          h('strong', {}, item.state === 'ok' ? '✓ ' : item.optional ? '○ ' : '✗ ', item.name),
          item.state !== 'ok' && item.fix && h('div', { class: 'ms-fix' }, item.fix)))),
          h('button', { type: 'button', onclick: async () => { await lookAgain(); draw(); } }, 'Look again')];
      },
      save: async () => {},
    },
    you: {
      title: 'You and your assistant',
      draw: () => {
        const agent = at('assistant', 'agent') || 'claude';
        return [
          field('Your name', h('input', { name: 'name', value: at('person', 'name'), maxlength: 100 }), 'Shown as the author.'),
          h('fieldset', {}, h('legend', {}, 'Assistant'),
            choice('agent', 'claude', 'Claude Code', agent === 'claude'), choice('agent', 'codex', 'Codex', agent === 'codex')),
          field('Model', h('input', { name: 'model', value: at('assistant', 'model'), placeholder: 'opus' })),
          field('Reasoning', h('select', { name: 'effort' }, EFFORTS[agent].map((level) =>
            h('option', { value: level, selected: level === (at('assistant', 'effort') || 'high') }, level)))),
        ];
      },
      save: () => save({ person: { name: value('name') },
                         assistant: { agent: picked('agent'), model: value('model'), effort: value('effort') } }),
    },
    work: {
      title: 'Where your work is kept',
      draw: () => {
        const team = Boolean(at('team', 'repository'));
        return [
          choice('where', 'local', 'On this computer', !team),
          field('Folder', h('input', { name: 'root', value: at('local', 'root') || '~/Studios' }),
            'trainings/, presentations/ and blogs/ go inside it.'),
          choice('where', 'team', 'In a team repository', team),
          field('Address', h('input', { name: 'repository', value: at('team', 'repository'), placeholder: 'https://github.com/acme/studios.git' })),
          field('Branch', h('input', { name: 'branch', value: at('team', 'branch') || 'main' })),
          h('fieldset', {}, h('legend', {}, 'Share'),
            choice('share', 'decision', 'After each decision', (home.shared.share || 'decision') === 'decision'),
            choice('share', 'asked', 'Only when I ask', home.shared.share === 'asked')),
        ];
      },
      save: () => picked('where') === 'team'
        ? save({ team: { repository: value('repository'), branch: value('branch') }, share: picked('share') })
        : save({ local: { root: value('root') } }),
    },
    brand: {
      title: 'Your brand',
      draw: () => [
        field('Brand skill repository', h('input', { name: 'brand-repository', value: at('brand', 'repository') })),
        field('Release', h('input', { name: 'release', value: at('brand', 'release'), placeholder: 'v1.4.0' })),
        field('Brand', h('input', { name: 'brand', value: at('brand', 'brand') })),
        field('Variant', h('input', { name: 'variant', value: at('brand', 'variant') }),
          'Install or upgrade the brand skill from any studio\'s Status page.'),
      ],
      save: () => save({ brand: { repository: value('brand-repository'), release: value('release'),
                                  brand: value('brand'), variant: value('variant') } }),
      skippable: true,
    },
    deliver: {
      title: 'Deliver as',
      draw: () => [choice('output', 'google', 'Google Slides and Docs', (home.shared.output || 'google') === 'google'),
                   choice('output', 'pptx', 'PowerPoint and Word files', home.shared.output === 'pptx')],
      save: () => save({ output: picked('output') }),
    },
  };

  async function lookAgain() { home.computer = (await call('/api/computer', {})).computer; }

  function drawSetup() {
    const name = STEPS[view.step];
    const current = step[name];
    const last = view.step === STEPS.length - 1;
    const next = async (skip) => {
      try {
        if (!skip) await current.save();
        view.problem = '';
        if (last) { home.setup = (await call('/api/setup', { done: true })).setup; view.screen = 'pad'; }
        else { view.step += 1; if (STEPS[view.step] === 'computer' && !home.computer) lookAgain().then(draw, show); }
      } catch (failure) { view.problem = failure.message; }
      draw();
    };
    return h('form', { class: 'ms-step', onsubmit: (event) => { event.preventDefault(); next(false); } },
      h('p', { class: 'ms-count' }, `Step ${view.step + 1} of ${STEPS.length}`),
      h('h2', {}, current.title), current.draw(),
      view.problem && h('p', { class: 'ms-problem', role: 'alert' }, view.problem),
      h('div', { class: 'ms-actions' },
        view.step > 0 && h('button', { type: 'button', onclick: () => { view.step -= 1; draw(); } }, '← Back'),
        current.skippable && h('button', { type: 'button', onclick: () => next(true) }, 'Skip for now'),
        h('button', { type: 'submit', class: 'ms-primary' }, last ? 'Finish →' : 'Next →')));
  }

  // --- launch pad ------------------------------------------------------------------------------

  async function open(studio) {
    try {
      const { link } = await call('/api/open', { studio: studio.id });
      window.open(link, `ms-${studio.id}`);
      home = await call('/api/home');
      view.problem = '';
    } catch (failure) { view.problem = `${studio.name}: ${failure.message}`; }
    draw();
  }

  function drawPad() {
    const studios = home.studios.filter((s) => home.setup.enabled.includes(s.id));
    const summary = [
      [at('assistant', 'agent') === 'codex' ? 'Codex' : 'Claude Code', at('assistant', 'model'), at('assistant', 'effort')].filter(Boolean).join(' · '),
      at('team', 'repository') ? `Team: ${at('team', 'repository')} (${at('team', 'branch') || 'main'})` : `On this computer: ${at('local', 'root') || '~/Studios'}`,
      at('brand', 'brand') ? `Brand: ${at('brand', 'brand')}${at('brand', 'variant') ? ' / ' + at('brand', 'variant') : ''}` : 'No brand chosen',
      `Deliver as: ${home.shared.output === 'pptx' ? 'PowerPoint' : 'Google'}`,
    ];
    return h('div', { class: 'ms-pad' },
      home.shared_problem && h('p', { class: 'ms-problem', role: 'alert' }, home.shared_problem),
      view.problem && h('pre', { class: 'ms-problem', role: 'alert' }, view.problem),
      h('div', { class: 'ms-cards' }, studios.map((s) => h('section', { class: 'ms-card' },
        h('h2', {}, s.name),
        h('p', {}, !s.installed ? 'Not installed' : s.running ? 'Running' : 'Not running'),
        s.installed ? h('button', { class: 'ms-primary', onclick: () => open(s) }, 'Open')
                    : h('small', {}, `Add it with: installer/install.sh --studios ${s.id}`)))),
      h('section', { class: 'ms-shared' }, h('h2', {}, 'Shared settings'), h('ul', {}, summary.map((line) => h('li', {}, line))),
        h('button', { onclick: () => { view = { screen: 'setup', step: 2, problem: '' }; draw(); } }, 'Change')));
  }

  // --- the page --------------------------------------------------------------------------------

  function draw() {
    const main = document.getElementById('main');
    const nav = document.getElementById('nav');
    nav.replaceChildren(home.setup.done ? h('span', {},
      h('button', { onclick: () => { view = { screen: 'pad', step: 0, problem: '' }; draw(); } }, 'Studios'), ' ',
      h('button', { onclick: () => { view = { screen: 'setup', step: 2, problem: '' }; draw(); } }, 'Settings'), ' ',
      h('button', { onclick: () => { view = { screen: 'setup', step: 1, problem: '' }; lookAgain().then(draw, show); draw(); } }, 'This computer'))
      : '');
    main.replaceChildren(view.screen === 'setup' || !home.setup.done ? drawSetup() : drawPad());
  }

  function show(failure) {
    document.getElementById('main').replaceChildren(h('p', { class: 'ms-problem', role: 'alert' }, failure.message));
  }

  (async () => {
    if (!KEY) return show(new Error('Open Marketing Studio from its window or Applications: the link it opens carries its key.'));
    try {
      home = await call('/api/home');
      if (!home.setup.done) view.screen = 'setup';
      draw();
    } catch (failure) { show(failure); }
  })();
  ```

  `home/page/home.css`:

  ```css
  /* Marketing Studio's own layout; type, colour and controls come from style.css (ui-kit). */
  .ms-top { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem 1.5rem; }
  #main { max-width: 64rem; margin: 0 auto; padding: 0 1.5rem 3rem; }
  .ms-step { display: grid; gap: .9rem; max-width: 40rem; }
  .ms-count { opacity: .7; margin: 0; }
  .ms-field { display: grid; gap: .25rem; }
  .ms-field small, .ms-fix { opacity: .75; }
  .ms-choice { display: block; padding: .2rem 0; }
  .ms-actions { display: flex; gap: .6rem; justify-content: flex-end; }
  .ms-problem { border-left: 3px solid currentColor; padding: .4rem .8rem; white-space: pre-wrap; }
  .ms-checks { list-style: none; padding: 0; display: grid; gap: .4rem; }
  .ms-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); gap: 1rem; margin: 1rem 0 2rem; }
  .ms-card, .ms-shared { border: 1px solid color-mix(in srgb, currentColor 20%, transparent); border-radius: .6rem; padding: 1rem 1.2rem; }
  @media (max-width: 40rem) { .ms-top { flex-direction: column; align-items: flex-start; } #main { padding: 0 1rem 2rem; } }
  ```

- [ ] **Step 4: Run every home test.**

  ```bash
  cd home && python3 -m unittest discover -s tests -t . -v
  ```

  Expected: all pass.
- [ ] **Step 5: Look at it.**
  1. Run `python3 home/scripts/marketing_studio.py` with `STUDIOS_CONFIG` pointing at a scratch file, so your real config is untouched:

     ```bash
     STUDIOS_CONFIG="$TMPDIR/sc.json" MARKETING_STUDIO_DATA="$TMPDIR/msd" python3 home/scripts/marketing_studio.py
     ```

  2. Walk all six steps.
  3. Confirm that `$TMPDIR/sc.json` holds what you typed.
  4. Confirm that the launch pad shows three cards.
  5. Check the layout at 375 px wide, in light and dark mode.
  6. Do not press **Open** yet. Studios accept the handoff only after Task 4.6.
- [ ] **Step 6: Commit:**

  ```bash
  git add -A home && git commit -m "Draw the home page: six set-up steps and the launch pad"
  ```

### Task 4.6: Studios accept the handoff

**Files:**
- Modify: `studios/training/runner/studio.py` (`handed_over`), `studios/presentation/runner/studio.py` (`handed_over`)
- Modify: `studios/blog/skills/blog-studio/scripts/start_studio.py` and `management.py` (key creation and announce, ~L1824 and ~L1900–1919 on origin/main 2.1.0)
- Test: `studios/training/tests/test_runner_studio.py`, `studios/presentation/tests/test_runner_studio.py`, `studios/blog/tests/test_management_ui.py`

- [ ] **Step 1: Write the failing test for Presentation.** Add to `studios/presentation/tests/test_runner_studio.py`:

  ```python
  class HandoffTests(unittest.TestCase):
      def test_a_key_handed_over_by_marketing_studio_is_used_and_not_passed_on(self):
          key = 'k' * 43
          os.environ['MARKETING_STUDIO_HANDOFF'] = json.dumps({'token': key, 'home': 'http://127.0.0.1:9/#token=H'})
          try:
              self.assertEqual(studio.handed_over(), key)
              self.assertNotIn('MARKETING_STUDIO_HANDOFF', os.environ)
              self.assertEqual(studio.HOME['link'], 'http://127.0.0.1:9/#token=H')
          finally:
              os.environ.pop('MARKETING_STUDIO_HANDOFF', None)
              studio.HOME.clear()

      def test_a_home_link_elsewhere_is_dropped(self):
          os.environ['MARKETING_STUDIO_HANDOFF'] = json.dumps({'token': 'k' * 43, 'home': 'http://example.com/'})
          try:
              studio.handed_over()
              self.assertNotIn('link', studio.HOME)
          finally:
              os.environ.pop('MARKETING_STUDIO_HANDOFF', None)
              studio.HOME.clear()
  ```

  Use the module's existing import name for `runner/studio.py`; check the top of the test file and match it.
- [ ] **Step 2: Run it.**

  ```bash
  cd studios/presentation && python3 scripts/ci/run_tests.py test_runner_studio.HandoffTests
  ```

  Expected: FAIL (`HOME` is not defined).
- [ ] **Step 3: Change `handed_over` in Presentation's `runner/studio.py`:**

  ```python
  HANDOFF = 'MARKETING_STUDIO_HANDOFF'      # the key and the home page, from Marketing Studio
  HOME: dict = {}                           # {'link': ...} when opened from Marketing Studio


  def handed_over() -> str | None:
      """The key handed to this runner: by a runner that stopped to open a newer version, or by
      Marketing Studio, which also says where its home page is. Both are taken out of the
      environment at once, so nothing this runner starts is given them."""
      restarted, opened = os.environ.pop(RESTART, None), os.environ.pop(HANDOFF, None)
      kept = restarted or opened
      try:
          given = json.loads(kept) if kept else {}
      except ValueError:
          return None
      if not isinstance(given, dict):
          return None
      link = given.get('home')
      if isinstance(link, str) and link.startswith('http://127.0.0.1:'):
          HOME['link'] = link
      token = given.get('token')
      return token if isinstance(token, str) and KEY.fullmatch(token) else None
  ```

  `serve()` already opens no browser when a key was handed over (`(lambda url: False) if token else opener`). One more line in `serve()` keeps the home link across a restart into a newer version. Change `os.environ[RESTART] = json.dumps({'token': studio.token})` to:

  ```python
      os.environ[RESTART] = json.dumps({'token': studio.token, 'home': HOME.get('link')})
  ```

  Then add a test, `test_a_restart_keeps_the_home_link`: set `RESTART` to `{"token": "k"*43, "home": "http://127.0.0.1:9/#token=H"}`, call `handed_over()`, and assert `HOME['link']`.
- [ ] **Step 4: Run it.** Use the same command as Step 2. Expected: PASS. Then run all of Presentation's checks:

  ```bash
  bash scripts/ci/check_all.sh python3 presentation
  ```

- [ ] **Step 5: Repeat Steps 1–4 for Training**, in `studios/training/runner/studio.py` and `studios/training/tests/test_runner_studio.py`, with `RESTART = 'TRAINING_STUDIO_RESTART'` as that file already defines it. The test and code are the same as in Steps 1 and 3.
- [ ] **Step 6: Blog.** Read where its key is made and announced:

  ```bash
  grep -n "token_urlsafe\|def announce\|isatty\|'url'" studios/blog/skills/blog-studio/scripts/management.py studios/blog/skills/blog-studio/scripts/start_studio.py
  ```

  Add to `start_studio.py`:

  ```python
  HANDOFF = 'MARKETING_STUDIO_HANDOFF'
  KEY = re.compile(r'[A-Za-z0-9_-]{32,128}')


  def handed_key() -> tuple[str | None, str | None]:
      """The key and home link Marketing Studio handed over, taken out of the environment."""
      kept = os.environ.pop(HANDOFF, None)
      try:
          given = json.loads(kept) if kept else {}
      except ValueError:
          return None, None
      if not isinstance(given, dict):
          return None, None
      token, home = given.get('token'), given.get('home')
      token = token if isinstance(token, str) and KEY.fullmatch(token) else None
      home = home if isinstance(home, str) and home.startswith('http://127.0.0.1:') else None
      return token, home
  ```

  Add `import re` beside the file's other imports if it is not there.

  - Pass the token into wherever `management.py` calls `secrets.token_urlsafe`, so that a handed key is used instead of a new one.
  - Pass the home link to the page state (Phase 6 uses it).
  - With `--json --no-open`, make sure the printed JSON has `"url"` without the key, which is its existing behaviour when not printing to a terminal.

  Test, in `studios/blog/tests/test_management_ui.py`, following that file's existing server-start pattern:
  1. Start the page with `MARKETING_STUDIO_HANDOFF` set.
  2. Assert that an API call with that key in `X-Blog-Studio-Token` is accepted.
  3. Assert that the variable is gone from `os.environ`.
- [ ] **Step 7: The real thing.**
  1. Run `python3 home/scripts/marketing_studio.py`, with scratch `STUDIOS_CONFIG` and `MARKETING_STUDIO_DATA` as in Task 4.5.
  2. Press **Open** on each card.
  3. Expected: each studio opens in its own tab, already holding its key. A second **Open** returns to that tab.
  4. Close the terminal window. Expected: every studio process ends. Check with `pgrep -fl 'studio.py serve|start_studio.py open'`, which should print nothing.
- [ ] **Step 8: Commit:**

  ```bash
  git add -A studios && git commit -m "Let each studio be opened by Marketing Studio with a key it was handed"
  ```

---

## Phase 5: Bundles and one installer

Re-check these files against the tree before starting. Each studio's installer is changing in open work.

### Task 5.1: `scripts/build_bundles.py`

**Files:**
- Create: `scripts/build_bundles.py`
- Create: `tests/test_build_bundles.py` (root `tests/`, added to `check_all.sh` as part `build`)

- [ ] **Step 1: Write the failing tests:**
  - `test_bundle_has_no_links`: walk `dist/marketing-studio-<v>/` and assert `not path.is_symlink()` for every path.
  - `test_each_studio_bundle_has_the_core`: assert `training-studio/skills/training-studio/scripts/studio_core/studios_config.py` is a real file.
  - `test_tests_and_docs_are_left_out`: assert there is no `tests/`, `docs/` or `.github/` inside any studio bundle.
  - `test_each_studio_validates`: run each studio's `validate_package.py` with `cwd` set to its bundle folder, and assert exit code 0.
  - `test_zips_are_written`: assert the suite zip and three studio zips exist, each with a `.sha256` file.
- [ ] **Step 2: Run them.** Expected: FAIL (no script).
- [ ] **Step 3: Write the script.**
  - It copies `home/`, `installer/`, `VERSION` and each `studios/<id>` to `dist/marketing-studio-<VERSION>/<id>-studio` (`home` stays `home`).
  - It uses `shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns('tests', 'docs', '.github', 'scripts/ci', '__pycache__', '*.pyc', '.DS_Store', 'node_modules', '.worktrees'))`.
  - It copies `pins/companions.json` into each studio's `installer/`.
  - It runs each studio's `validate_package.py` inside its bundle and stops on the first failure.
  - It writes zips with `shutil.make_archive` and their `.sha256` files with `hashlib.sha256`.
  - It reads the version from `VERSION`.
  - Its command line is `build_bundles.py [--out dist]`.
- [ ] **Step 4: Run the tests.** Expected: pass.
- [ ] **Step 5: Commit:** `Build each studio and the suite with the core copied in`.

### Task 5.2: The suite installer

**Files:**
- Create: `installer/install.py`, `installer/install.sh`, `installer/Install Marketing Studio.command`, by copying `studios/training/installer/*` and adapting
- Create: `installer/tests/test_install.py`, adapted from `studios/training/tests/test_installer.py`

Each behaviour is written as a failing test first, then implemented. Each test runs the installer against a fake `HOME` (`--home <tmp>`, as Training's installer tests already do):

- [ ] **`test_installs_suite_layout`:** after an install, these exist:
  - `<home>/.local/share/marketing-studio/current/home/scripts/marketing_studio.py`
  - `<home>/.claude/skills/training-studio`, a link resolving into `current/training-studio`
  - `<home>/.agents/skills/training-studio`, likewise
  - `<home>/Applications/Open Marketing Studio.command`
  - `<home>/.local/share/marketing-studio/marketing-studio`, executable
- [ ] **`test_studios_opt_in`:** `--studios training,blog` links only those two skills, and records `enabled` in `installation.json`.
- [ ] **`test_companions_once`:** companions are fetched once at the pinned commit and linked into both skill folders. Reuse Training's companion test stand-ins.
- [ ] **`test_refuses_while_a_studio_serves`:** a live `runner.pid` (this test's own pid) in `<home>/.local/share/training-studio/` makes the install refuse with the existing sentence.
- [ ] **`test_migrates_a_standalone_install`:** given a fake standalone Training install (`<home>/.local/share/training-studio/current -> versions/x`, its skill link and `Open Training Studio.command`), the suite install:
  - renames `current` to `current.pre-suite`,
  - writes `"moved_to": "marketing-studio"` into the old `installation.json`,
  - re-points the skill link,
  - rewrites the old `.command` to run `marketing-studio open training`,
  - and leaves `runner.json`, `workspace.json` and `workspaces/` byte-for-byte unchanged.
- [ ] **`test_uninstall_restore_standalone`:** reverses the migration above exactly.
- [ ] **`test_rollback`:** moves `current` to the previous suite version in `installation.json` history.
- [ ] **`test_check`:** prints one JSON object per studio with `installed`, `version` and `missing[]`, and exits 0.
- [ ] **Commit after each passing behaviour,** with messages such as `Install the studios as one suite` and `Move a studio installed on its own into the suite, keeping its data`.

### Task 5.3: Studio upgrade buttons defer to the suite

**Files:**
- Modify: `studios/training/runner/upkeep.py`, `studios/presentation/runner/upkeep.py`
- Test: their `tests/test_runner_upkeep.py`

- [ ] **Step 1: Write the failing test.** When `<home>/.local/share/marketing-studio/installation.json` exists and lists this studio, `Upkeep.report()` gains `{"suite": {"home": "marketing-studio"}}` and offers no `upgrade` action of its own.
- [ ] **Step 2: Implement** the check in `Upkeep.report()` and in the `/api/upgrade` handler (`runner/page.py`), which refuses with "Update from Marketing Studio: open it and choose Versions."
- [ ] **Step 3:** In `app.js`, where the Versions card draws its **Upgrade** button, draw "Update from Marketing Studio" text instead when `report.suite` is set.
- [ ] **Step 4: Run** `check_all.sh python3 training presentation`. Then commit: `Leave upgrades to Marketing Studio when it installed the studio`.

### Task 5.4: Versions on the home page

**Files:**
- Modify: `home/scripts/page.py` (read `/api/versions`; write `/api/upgrade`, which runs the installed `installer/install.py upgrade` in a child process and answers its JSON)
- Modify: `home/page/app.js` (a Versions screen with Installed / Newest / Pinned, and an **Update** button)
- Test: `home/tests/test_page.py` (`test_versions_lists_suite_studios_and_companions`, `test_upgrade_runs_the_installer`, with the installer stood in by a fake script, the same pattern as `fake_studio.py`)

Steps: failing test → implement → run → commit, as in Task 4.3. Message: `Show and update every version from the home page`.

---

## Phase 6: Studios meet the home page

### Task 6.1: The Marketing Studio link back

**Files:**
- Modify: Training and Presentation `runner/setup.py` (`describe()` adds `'home': studio.HOME.get('link')`, imported from the `runner/studio.py` module state), and `app.js` (sidebar)
- Modify: Blog `management.py` (state adds `home`), `runner.js` (header)
- Tests: `test_runner_setup.py` (`describe` includes `home` when handed over and is `None` otherwise); `test_desk.py` / `test_page_app.py` (the link is drawn with `target="ms-home"` and `rel="opener"` only when `home` is set)

- [ ] **Step 1:** Failing tests as listed.
- [ ] **Step 2:** In each `app.js`, find where the sidebar header is drawn:

  ```bash
  grep -n "sidebar" studios/*/skills/*/scripts/desk/app.js | head
  ```

  Add, using that file's own element helper:

  ```javascript
  if (state.home) header.prepend(el('a', { href: state.home, target: 'ms-home', class: 'home-link' }, '← Marketing Studio'));
  ```

  Use the file's existing names for `state`, `header` and the element helper.
- [ ] **Step 3:** Run each studio's checks. Commit: `Lead back to Marketing Studio from each studio it opened`.

### Task 6.2: "Start with your Marketing Studio settings"

**Files:**
- Modify: Training and Presentation `runner/setup.py`: add `quick_start(values) -> dict | None`, which returns the workspace and defaults to use when the shared values cover what set-up needs, and `None` otherwise.
- Modify: Training and Presentation `runner/page.py`: POST `/api/setup/quick`, which joins or creates the workspace from `quick_start` exactly as the full set-up form would.
- Modify: each `app.js`: when `setup.configured` is false, `HOME.link` was set and `quick` is present, draw one card instead of the form.
- Blog: the same in `blog_runner.py` and `runner.js`.

Tests, failing first:

- `quick_start` covers:
  - (a) `local.root` set, so it gives a local workspace at `<root>/presentations`;
  - (b) team repository, branch and share set, so it gives a team join of folder `presentations`;
  - (c) agent missing, so it gives `None`;
  - (d) an existing workspace, so it gives `None`, because existing work never moves.
- `/api/setup/quick` creates the same workspace record as the full form, for the same values. Compare `workspace.json`.
- The page draws the card only when opened from home.

Commit: `Start a studio with Marketing Studio's settings in one click`.

### Task 6.3: `local.root` in suggestions

**Files:**
- Modify: Training and Presentation `runner/setup.py` (`suggested(values)`), and Blog's start path. The home launcher passes `--root <local.root>/blogs` when `local.root` is set and Blog has no remembered workspace.
- Tests:
  - `suggested({'local': {'root': '~/S'}})` gives a local path of `~/S/presentations`, expanded.
  - Blog: the launcher adds `--root` only when the shared value is set.

Commit: `Suggest a folder under the shared one for work kept on this computer`.

### Task 6.4: "Needs you" counts on the cards

**Files:**
- Modify: Training and Presentation `engine.status()` (adds `summary: {"waiting": n, "working": n}`); Blog `start_studio.py status --json` (new action, same shape)
- Modify: `home/scripts/page.py`: `GET /api/home` runs each enabled, installed studio's status command in a child process at most once every 30 s, with a 10 s timeout, and adds `summary` to each studio. A failure becomes `summary: null`, never an error.
- Modify: `home/page/app.js`: a card shows "N need you" when `summary.waiting > 0`.
- Tests:
  - each studio's status test asserts the `summary` shape;
  - `home/tests/test_page.py` uses a fake status script to assert caching, timeout and the `null` case.

Commit: `Show on the home page what is waiting in each studio`.

---

## Phase 7: The rest of the core

Each step follows the same recipe. Do one module per task and one commit per task. Before each task, re-read the module in every studio, because these are under active change.

**Recipe:**

1. Diff the copies, normalising the product names:

   ```bash
   diff <(sed 's/Presentation Studio/X/g;s/presentation/x/g' A) <(sed 's/Training Studio/X/g;s/training/x/g' B)
   ```

   Pick the copy with the most fixes. List every behaviour the other copy has that it lacks, and add each to the chosen copy with its test.
2. `git mv` the chosen copy to `core/studio_core/<module>.py`. Remove product names (use `PRODUCT`). Pass in paths the studio owns.
3. Move its tests to `core/tests/`, adjusting imports as in Task 3.2 Step 4.
4. Replace each studio's copy with a re-export that sets `PRODUCT`, as in Task 3.2 Step 5.
5. Remove its entries from Presentation's `vendor.json` and Blog's vendoring records.
6. Run `bash scripts/ci/check_all.sh python3`. Expected: all pass.
7. Commit: `Keep <module> in the core`.

| Task | Module(s) | Studios today | Notes |
|---|---|---|---|
| 7.0 | — | — | Write `docs/core-status.md`: one row per copied module, listing where each copy lives and its drift in lines. Update it after each task. When Presentation's `vendor.json` is empty, delete it. |
| 7.1 | `gitstate`, `team` | Training, Presentation; Blog `studio_sync` | Presentation's adapted copy reads share mode from the studios config (issue #70); keep that behaviour. |
| 7.2 | `hub` | Training, Presentation, Blog `hub*.py` | `ADDRESS_WITH_SECRET` already lives in `studio_core.addresses`. |
| 7.3 | `brand_source`, `brand` | Training, Presentation at 0881ce7; Blog `studio_brand` | Then add **Install brand skill** to home step 5 and Settings: POST `/api/brand/install` in `home/scripts/page.py`, calling `studio_core.brand_source`. Test with the brand stand-ins in `studios/*/tests/stand_ins/brand.py`. |
| 7.4 | `companion`, `upkeep` (the companion parts) | Training, Presentation (1,094 lines of drift) | Reads `pins/companions.json` through the installer's copy. Home's Versions uses it directly. |
| 7.5 | `agents`, `jobs` (engine machinery: turns, claims, halting, sharing) | Presentation split `jobs.py` out | Pipelines stay in each studio's `engine.py` / `steps/`. Only what both import unchanged moves. |
| 7.6 | `computer` for Blog | Blog's own shape (`checks[]`, `status`) | Either make Blog read the core shape, mapping its own keys, or keep Blog's. Decide by diff size and record the decision in `docs/core-status.md`. |
| 7.7 | `server` for Training (`desk.py`) | Training | Training's `desk.py` subclasses `studio_core.server.Page`, as Presentation's does since Task 3.3. |

---

## Phase 8: Cutover

### Task 8.1: Publish this repository

- [ ] **Step 1:** Ask the user before creating anything public or private on GitHub. Then:

  ```bash
  gh repo create dbbaskette/marketing-studio --private --source . --push
  ```

  Choose the visibility the user picks.
- [ ] **Step 2:** Confirm CI runs green on `main` (all five parts).

### Task 8.2: Move open issues

- [ ] **Step 1:** List open issues in each old repository:

  ```bash
  for r in training-studio presentation-studio blog-studio; do gh issue list -R dbbaskette/$r --state open; done
  ```

- [ ] **Step 2:** With the user's go-ahead, run `gh issue transfer <n> dbbaskette/marketing-studio -R dbbaskette/<r>` for each issue. Add the label `studio:<id>`.

### Task 8.3: First suite release

- [ ] **Step 1:** Write `scripts/release.sh`, adapted from Blog's:
  1. Run `python3 scripts/build_bundles.py`.
  2. Then run:

     ```bash
     gh release create "v$(cat VERSION)" dist/*.zip dist/*.sha256 --notes-file docs/release-notes.md
     ```

- [ ] **Step 2:** Write `docs/release-notes.md` for the first suite release, using the number chosen in §1.15 question 4. Cover what changed for someone who used a studio on its own: one installer, one page, and their data untouched.
- [ ] **Step 3:** Ask the user before running `scripts/release.sh`.

### Task 8.4: Point the old repositories here

- [ ] **Step 1:** In each old repository, replace `README.md` with a short pointer:

  ```markdown
  # <X> Studio has moved

  <X> Studio is now part of [Marketing Studio](https://github.com/dbbaskette/marketing-studio),
  with Training, Presentation and Blog Studio installed and set up together. Your work and
  settings carry over: run its installer and it moves this studio in.
  ```

  Commit and push that README only, after asking the user.
- [ ] **Step 2:** Archive each repository with `gh repo archive dbbaskette/<r>`, after asking the user. For Blog, follow the answer to open question 1 (§1.15) first.

### Task 8.5: Docs

- [ ] **Step 1:** Root `README.md`: install, first run (the six steps), opening a studio, where data lives, updating, rolling back, and uninstalling (including `--restore-standalone`).
- [ ] **Step 2:** Move `studios/presentation/docs/shared-studios.md` to `docs/shared-studios.md`. Add the `local` group (§1.8). Leave a one-line pointer at the old path.
- [ ] **Step 3:** Commit: `Say how to install and use Marketing Studio`.

---

## Self-review

**Spec coverage.** Every spec section maps to tasks:

| Spec | Tasks |
|---|---|
| §1.4 layout | 1.1–1.5, 3.1, 3.5, 4.1 |
| §1.5 core | 3.1–3.5, 7.0–7.7 |
| §1.6 pins | 2.1 |
| §1.7 home: process | 4.2, 4.4, 4.6 |
| §1.7 home: security | 4.3 tests, using the core server |
| §1.7 home: data | 4.3 |
| §1.7 home: API | 4.3, 5.4, 6.4 |
| §1.7 home: screens | 4.5, 5.4, 6.4 |
| §1.8 `local.root` | 3.2, 6.3 |
| §1.9 studio changes | 4.6, 5.3, 6.1–6.4 |
| §1.10 installer | 5.1–5.4 |
| §1.11 migration | 0.1–1.4, 8.1–8.4 |
| §1.12 errors | 4.2 and 4.3 tests (refusal, timeout, exit, bad address, stale value, unreadable config); 5.2 (refuse while serving) |
| §1.13 testing | 1.5 CI, every task's tests |

**Names used across tasks:**

- `HANDOFF` / `MARKETING_STUDIO_HANDOFF`: `catalog.py`, the studios and `fake_studio.py`.
- `Launcher.open`, `running` and `stop`: Tasks 4.2, 4.3 and 4.4.
- `page.factory` and `HomePage.launcher`: Tasks 4.3 and 4.4.
- `studios_config.PRODUCT` and `GROUPS` with `local`: Tasks 3.2 and 3.4.
- `choices.check`: Tasks 3.4 and 4.3.
- `server.Page(port, token)`, `token_header`, `page_dir`, `files` and `product`: Tasks 3.3, 4.3 and 4.4.
- `HOME['link']`: Tasks 4.6 and 6.1.

**Known soft spots** (on purpose, because the code underneath is moving):

- Tasks 3.2 Step 3, 3.3 Step 3 and 4.6 Step 6 copy existing lines or follow an existing pattern instead of reproducing them here.
- Phases 5–8 give tests and behaviours, not full code.
- Each says what to read first. Re-check them when the phase starts.
