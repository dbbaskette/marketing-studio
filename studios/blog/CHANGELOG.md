# Changelog

Releases are published from `skills/blog-studio/VERSION`. Each entry says what
changes for authors first, then what changes for maintainers.

## 2.0.0

Blog Studio is now installed as one complete skill. The earlier design, a small
bootstrap that fetched instructions from the repository at the start of every
blog, is retired.

**For authors**

- **Install and update from Releases.** Download `blog-studio-installer.zip`
  from the latest release and run `sh installer/install.sh`. Updating is the
  same step with a newer download.
- **No repository access or GitHub sign-in to write.** Setup and writing work
  offline. Git and the GitHub CLI are needed only for a Team Hub.
- **Starting a blog is immediate.** Nothing is fetched or copied per blog, and
  the `task-context` folder is no longer used.
- **Each blog records the version it was started with.** Say “Use the current
  guidance for this blog” to adopt the installed version; earlier reviews are
  then marked stale. Blogs started in 1.x keep opening and saving.
- **Setup is harder to break.** It no longer depends on a Homebrew path that
  disappears on a Python upgrade, and `check` reports a missing Python. A closed
  window or crashed setup no longer blocks the next run. An interrupted update
  is undone or completed. Running setup over a damaged installation replaces
  it. Finder's `.DS_Store` files no longer fail verification.
- **Backups stay out of skill folders.** A replaced folder moves to
  `~/.local/share/blog-studio/backups/`, so tools do not discover it as a
  second Blog Studio. Setup asks before moving anything.
- **Update, repair and check keep your tools.** Without `--target` they act on
  the tools chosen at installation.
- **Rollback works for every installed version**, including each 1.x release.

**Upgrading from 1.x:** run the 2.0 installer; it upgrades in place. Until
then a 1.x installation answers a new blog with “This guidance needs a newer
local Blog Studio runtime. Run the installer update.” Existing 1.x blogs can
still be resumed there.

**For maintainers**

- One version source: `skills/blog-studio/VERSION`.
- `bootstrap/`, `sync_guidance.py` and the committed `dist/` archives are
  removed. `scripts/build.py` builds reproducible archives into the ignored
  `build/` folder and replaces both packaging scripts.
- `release.yml` tags and publishes a GitHub Release when `VERSION` changes on
  `main`. `ci.yml` and the release run the single list in `scripts/ci/check.sh`.
- `studio.py article guidance` takes `--id` and optional `--adopt`; `--task`
  and `--cached` are gone. `readiness --online` is accepted and does nothing
  extra.
- `guidance/manifest.json` stays as the upgrade notice for 1.x installations.

## 1.0.0 to 1.15.0

Condensed from the per-release notes that used to live in the installation
guide. All of these releases used the bootstrap design.

- **1.15** Deep research: “Research this topic”, “Fact-check” and saved research
  briefs, with the research workflow bundled in the installer.
- **1.14** Normal Git checkouts for Team Hubs under `~/blogs/`, visual import of
  earlier blogs in the editorial desk, reusable reference memory, and “Push
  feedback as comments”.
- **1.13** Drafts, originals, reviews and history kept together in readable
  folders inside each Hub.
- **1.12** Editorial desk and the shared team blog library.
- **1.11** “Start from this Google Doc”, which keeps the original Doc linked as
  the working document.
- **1.10** Readable review comments when native Google suggestions are
  unavailable, with “Show review edits” and “Apply edits 2 and 4”.
- **1.9** “Push as suggestions”, with a freshness check of the linked Doc first.
- **1.7 and 1.8** Short commands, status cards and writing defaults; faster
  local resume and checks.
- **1.5 and 1.6** Formatted Google Docs round trips, optional house style, live
  Google freshness and Doc links in the Hub library.
- **1.2 to 1.4** Google Docs workflows and transfer checkpoints, the gcloud
  route, guided writing and the readable team library.
- **1.1** Team Hub: shared blogs, sources, voices and team rules in a private
  repository.
- **1.0** Guided installer and pinned guidance updates.
