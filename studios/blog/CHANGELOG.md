# Changelog

Releases are published from `skills/blog-studio/VERSION`. Each entry says what
changes for authors first, then what changes for maintainers.

## Unreleased

- Research stops now show the authored brief, independent check, gaps, partial sources
  and findings mapped to planning questions. Research requests describe the full rerun,
  recorded cost and saved downstream work before sending. Home preserves research defaults.
- Supplied-only guided blogs map claims to exact source passages with one correction
  instead of researching their own material. Web research gets a tool-less plan of at most
  eight questions. Saved legacy pipelines and from-files supplied-only runs retain their flow.

- **Where this run stops, and one name for each thing.** The last step of a new blog has
  a **Where this run stops** card: the level for this blog, the stops it makes, and
  **Use this for new work in every studio**; Settings has **Where new work stops**, saved
  at once and refused when another studio changed it meanwhile. A run says how many
  steps are left, where it next stops and what its jobs have cost (every stage job is now
  metered, not only research), and **Ask for changes** says what is drawn again and what
  that took last time. The last stage is the **Handoff**; **Publish revision** is
  **Record in team repository**; the research choice reads **No research**, **Only what
  you supply** or **What you supply and the public web** everywhere; the form says what
  research will read, what the tone does beside a voice, and each gate says what its
  decision does. The README lists Home's real start choices. For maintainers:
  `studios_config.update` takes a `guard`, the run view has `ahead` and `redo`, and stage
  jobs are kept in this computer's run state as `jobs`.
- **Research that can finish, and failures that say what to do.** Research the
  independent check refused is no longer thrown away: the draft report and the check's
  notes are kept on this computer, in the blog's `.studio-research-draft` folder (never
  shared), and the run lists **What the research check objected to**, grouped by kind and
  verdict with the first note of each. **Try again** continues from that draft for up to
  three more rounds and says what the last attempt took; research says "Round 2 of 3"
  while it works. A new blog stopped at research offers **Continue without research**
  instead of pointing at an Edit manuscript button it does not have. **Finish** asks
  first at every review level and says the draft is kept in the team library, then
  "Finished. Kept in the team library." A CLI failure points at **Status → Check this
  computer** and shows **What the assistant said**; a step out of time says how long a
  step may take and that the limit is in Settings. First-run setup opens **Writing
  preferences** and marks an assistant that is not installed.
- For maintainers: the run's local state carries `reason` (`cli`, `time-limit`,
  `research-check`), `said` (the last 20 stderr lines, kept in
  `.blog-runs/diagnostics/cli/<id>.json`, mode 0600) and `research` (`kept`, `refusal`,
  `round`, `phase`, `last`, `contract`, `from`); `said` is redacted and drops lines that
  echo the job, and is kept only for a CLI failure. The kept draft's `kept.json` ties it to
  the research stage's pin and saved version, and saving research by any path lets it go.
  Status carries `research_skipped` and `keeps_draft`. The page route `run-skip-research`
  drops the research stages (not while research awaits a decision) and records
  `research_skipped`; later jobs get `research_policy: none` and no
  `research_bundle`. `synthesis_research.generate` takes `progress`, and
  `blog_worker.metered()` collects the tokens and dollars a CLI reports. The refusal
  takes the shared contract's `groups` and `cause` when it has them.

- **A Google Doc with several tabs is read whole.** Adding a Doc link to a blog's files
  reads every tab, each under its own title, and the file row says which tabs were read.
  A link to one tab (the address Google Docs shows for that tab) reads that tab alone. Such
  a Doc used to be refused with a message about snapshots, and Start stayed grey without
  saying why; the files screen now says it needs one file with text.
- **One team library.** Every finished blog lands in the library when you choose
  **Finish**, as a reference and an example of its kind of post by its author; a second
  Finish updates the same item. Files added to a blog land there too unless you untick
  **Keep in the team library**. **Add to library** takes files, a list of links and a
  Google Doc in one sheet with a role, author and kind of post; **Each post's own
  author** reads every page's byline and groups the posts by author to rename, merge,
  complete, mark as voice samples and learn a voice from. The library filters by role,
  kind and author, and a selection learns a style or a voice or starts a blog with the
  items as examples. **From the library** on the files card picks items as facts or
  examples for one blog without changing them, and a learned kind of post pre-ticks the
  examples it was learned from. **Settings** names a default voice, and **Interview me**
  takes **Write as**.
- For maintainers: a source's `library` record carries `kind`, `origin_kind` and
  `article`; `library find` takes `--role` and `--kind`; `run create` takes `--example
  <id>` and, from the page, `library: [{id, role}]`; `source-role` changes a library
  reference in a new revision; the desk routes are `library-add-preview`, `library-add`,
  `library-add-author`, `library-add-samples` and `library-selection`; the personal
  writing default `voice` is saved from Settings, checked against `voice_before`. A Team
  Hub row is named with `location: hub` and checked out before use; `library-add` takes
  `retry` for failed links; `library-selection` saves nothing, and a confirmed learning
  job with `mark` makes its chosen items samples. A run reads every source at the
  revision it pinned, from `revisions/<n>/` when the source has moved on.
- Deleting a blog accepts its title as you type it: case, spacing, curly quotes and
  dashes no longer have to match the stored title exactly, and the sheet says when
  the text is not the title yet. Every card on **Blogs** has **Delete**.
- **Voices and styles.** A blog takes a voice (how you sound) and a style (the shape of a
  kind of writing), chosen as **Write as** and **Kind of post** when you start it. Eight
  starter styles for tech-industry writing are ready to use and editable, and a style can
  be learned from examples of a kind of writing by anyone. **Tools → Voices and styles**
  manages both in one place, and **Change the voice** switches a blog's voice, asking
  first when it already has writing. **More tools** is now simply **Tools**.
- **Write as someone else.** A voice belongs to one author, so a ghostwriter can keep a
  voice for each person they write for and start a blog with that person's voice and name.
- **Bring in writing, yours or an author's you write for.** Import a LinkedIn data export
  (profile and articles only), paste links or choose a links file of public posts and say
  whose they are, or use a source already in your references. Each becomes that author's
  sample, and the sheet offers to learn their voice, or a style, from them.
- **In chat, a blog takes your default voice** when you do not name one, as on the page,
  and a revision or review keeps its manuscript's own voice. Ask for no particular voice
  to write without one; a tone you give beside a voice nudges it, and a kind of post
  can be named too.
- For maintainers: styles are stored beside voices in a `styles` folder (and `.shared/styles`
  in a team workspace), starters are copied in only when saved, retired or used, and
  `library voice-links` takes `--purpose style-sample`. `run create` applies the default
  voice without `--profile`, `--profile ''` asks for none, and `--style <id>` pins a style.
- **Write from a brief** takes every file at once, like New blog from my files: the
  second step lists each file with how much text it has and what it is for, takes a
  Google Doc beside them, and keeps the saved references and research choice in their
  own disclosure. Files stay with the blog unless you keep them in your references.
  Oversized files are excerpted on every path, and a blog pins the files it was given
  so a deletion keeps them with it.
- **New blog from my files** asks what each upload is for: facts that may be quoted,
  or an example of the kind of post. Examples reach the assistant apart from the
  sources, with no citable ID; research never reads them; the draft and review say
  which passages were carried over from one, under **Checked for you**.
- **I know the point** starts a blog from files at the outline, from a title, the
  point and the reader, instead of three angles. **Write as** chooses the voice on
  the files screen as on the wizard's first step: your default voice, at the revision
  it pins, a saved profile or none.
- Under Balanced, a blog that starts from your outline stops for you at the draft
  before its package; so does a revision, and an existing blog after changes to its draft.
  A run that selected an inspiration source before this change goes stale, because
  its saved input pins change; review its saved version or ask for changes to go on.
- For maintainers: `upload` file entries take `purpose`; the `source-role` desk route;
  `run create --point`; `run-create` takes `revision` beside `profile`; `review_policy.automatic(..., first=)`;
  `text_checks.carried_over`; `synthesis_research.offered`.

## 4.3.0 — 2026-10-20

- Manuscript **More tools** adds voice learning, auditions and revisions; resumable
  interviews; channel copy; Google/local comparison; text history; citation/title
  workshops; local pre-publish reports and topic-overlap advice.
- Results remain reviewable. Local saves, shared delivery, Google sends, profile
  confirmation and draft approval stay separate. Source changes reject older output.
- Library status/collection filters and retirement undo improve recovery. Long
  sheets keep Close reachable, with the existing keyboard focus and phone layout.
- Optional `--compact` command results and a generated command inventory make CLI
  outcomes easier to consume without changing compatible full JSON.
- Git tree reads reuse exact immutable revisions within one bounded operation;
  nothing caches remote freshness or changes published history.
- See [capabilities](docs/capabilities.md), [privacy](docs/privacy-review.md) and
  [optional proposals](docs/optional-extensions.md) for limits and future scope.

## 3.0.0 — 2026-10-15

**For authors**

- Shared Settings conflicts now offer an explicit reload and retry. Reloading
  keeps local writing preferences and shows the current shared values.
- Joining a team checks for concurrent Settings changes before preparing the
  clone and before activating it. A refusal keeps the previous active workspace
  and the other studio's settings. Local writing saves preserve an unsupported
  shared assistant and its model/effort.

**For maintainers**

- Blog Studio, Training Studio and Presentation Studio now share one release
  number, and all three are 3.0.0. The major version marks that shared number;
  nothing authors rely on was removed, and existing blogs, voices and settings
  carry over unchanged.
- Refresh the backlog for the current page and shared workspaces; closed
  live-evidence issues are no longer described as implementation gates.

## 2.1.0 — 2026-10-15

**For authors**

- Add a brand skill's repository and release in Settings, select an installed
  skill, and install a checked release after confirmation, like Training Studio.
  Choose a brand and variant for each new blog; existing blogs retain their exact
  brand guides and keep the author's voice separate.

- Join one team repository alongside Training and Presentation Studio. Blogs use
  readable folders, one confirmed driver, explicit takeover/handover, decision
  sharing and numbered revisions. Selected legacy Hub work can be migrated while
  preserving its source. Shared studios settings live in one file, edited directly from
  Settings. Legacy local copies migrate without overwriting existing shared values.

- Open Blog Studio with a permanent shell command or Mac launcher, like Training
  Studio. Setup and the UI share computer checks with actionable next steps. Start
  commands find a supported Python and remember your selected writing workspace.
  Updates preserve custom launchers and wait until the running page is closed.

- Use Training Studio’s current page layout, navigation, three-step creation,
  progress stages, paper reviews and approval sheets, with Blog Studio modes
  for writing, outlining, revising and reviewing. Edit shared settings and local
  writing preferences in Settings, and compare a revision with its last approved version.
- Create and run guided blogs from the page, or work through the same stages
  with the skill in a conversation. Research questions, findings, outline,
  draft, review and export package each wait for your approval.
- Select your sources, voice, research scope and Codex or Claude CLI. Pause,
  stop, retry, download Markdown, ask for changes to an earlier stage, or
  continue the same blog in chat. Existing manuscripts can enter at review.
- Changed inputs invalidate decisions. Old page actions and late worker results
  cannot replace newer saved work. Runs and decisions share through the existing
  Hub; execution starts only on computers where you explicitly resume it.

**For maintainers**

- Releases are published with `bash scripts/release.sh` from a clean, current
  `main`. The `release.yml` workflow added in 2.0.0 is removed: the runner
  service that checks pull requests serves this repository only while its one
  approved workflow is the only active one, so a second workflow stopped every
  pull request check.
- `verify-tart.yml` is back to its approved content. `check.sh` now requires
  the linter whenever it runs under GitHub Actions, so the workflow does not
  have to ask for it.

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

- **Team Hub stays usable as it grows.** Earlier drafts are shared once
  instead of with every save, so a blog no longer hits the Hub size limit after
  a few dozen saves. Local snapshot copies that nothing read are gone, and
  delivered saves leave the local queue.
- **An interrupted command no longer blocks the next one.** A second command
  waits briefly for the first instead of failing with "Workspace is busy".
- **No silent second version.** If a teammate shared a newer version of a blog,
  your save is kept on your computer and reported as held; you choose to
  continue from the shared version or share both and resolve them.
- **Clearer Hub failures.** A closed contribution review is retried on a new
  one; local Git problems are reported as such instead of as "offline"; an
  oversized source is refused at intake with the file and limit named.
- **The editorial desk only changes what you changed.** Saving an owner or due
  date no longer renews a stale "ready" decision, and saving a note no longer
  freezes a reference's tags. Marking a blog ready or published asks you to
  confirm.
- **The desk stays up.** A bad Word file, a damaged search index or one
  unreadable blog produces a message instead of a dropped connection, and a
  slow request no longer freezes every tab.
- **Importing earlier posts is cleaner.** A failed preview leaves no empty
  collection behind, refreshing a folder picks up new files, and re-importing
  does not duplicate posts.
- **You choose whether a reference is summarized.** Upload and import dialogs
  say that summaries send the document text through your signed-in writing
  CLI, and each has a checkbox to skip it. Opening the desk no longer turns
  summaries on by itself.

- **Google review can always be continued.** A timed-out or refused
  suggestion, a comment batch interrupted by a rate limit, and an uncertain
  "Apply edits" can each be verified and resumed instead of blocking the blog.
  Review edits are numbered per blog, so a second round does not reuse "Edit 1".
- **Edits on both sides are merged.** When you and a teammate changed different
  paragraphs, pulling combines them; only a paragraph changed on both sides
  asks you to choose. With a linked Doc, "Proofread" saves findings and leaves
  your draft alone, so rejecting a suggestion no longer ends in a conflict.
- **Fewer false stops.** A teammate's pending suggestion no longer blocks
  starting from, pulling, or commenting on a Doc. Renaming a Doc is not treated
  as a change. Strikethrough, underline, superscript, code and titles survive a
  pull, and inserted words no longer inherit a neighboring link or bold.
- **Google data stays closer to home.** A Doc's raw data, which can include
  collaborators' comment threads, stays on your computer instead of syncing to
  the Team Hub. Staged captures are cleaned up, writes are limited to Docs
  linked to a blog, the Google account is remembered per workspace, and sign-in
  no longer switches the account gcloud is using.

Known limits: a Doc with tables, images or footnotes cannot be pulled while
suggestions are pending; a Hub that was already large keeps its earlier history;
and everyone sharing a Hub should update to 2.0 together. Google behavior was
verified against recorded fixtures, not a live account.

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
