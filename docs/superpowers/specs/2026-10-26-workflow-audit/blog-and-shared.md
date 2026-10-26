# Audit: Blog Studio after the writing desk, and Marketing Studio home and shared setup

Read-only, main at cc53056, 2026-10-26. Line references are to that commit.

## Part A.1 Broken or dead-end paths

Ranked by what a person loses. Paths are relative to `studios/blog/skills/blog-studio/`.

1. **A desk blog driven by another computer cannot be taken over.** Every desk write in a team workspace runs `team_workspace.guard`. That raises `studio_sync/team.py:172` "…It can be read here. Take it over to change it." or `:77` "Nobody is running this blog. Take it to carry on with it from this computer." `desk.js` has no Take, Take over or Hand over; those exist only on a run (`runner.js:254`). The server path fails too: `team-*` routes require `expected`, and `team_workspace.action` (`:403-405`) calls `blog_runner.survey`, whose `load` raises "This blog has no guided run" for a desk blog (`blog_runner.py:564`). No test covers taking over a desk blog. The desk blog stays read-only for teammates.
2. **A stopped desk start can only Retry.** The page says "This start stopped before the draft was ready. Retry the step when you are ready." (`desk.js:278`), and Retry runs the same step again (`desk_jobs.py:1186`). A research refusal, a time-out or a CLI failure gets none of the Phase 1 exits: no "Continue without research", "Try again with more time", "Open Status" or "What the assistant said" (those are `runner.js:85-90, 254`, run-only). The only way on is to delete the blog from the lists and start over.
3. **Restoring a deleted desk blog dead-ends.** Restore routes to the run screen with the toast "It stays stopped until you resume it." (`runner.js:1069`). A desk blog has no run, so the page shows "This view could not be read" (`runner.js:119`) with "This blog has no guided run. Choose Run this blog on the page." (`blog_runner.py:564`). There is no "Run this blog" control anywhere. The blog does come back, but only Home or Blogs reaches it.
4. **A desk blog can never get a Google Doc.**
   - The desk toolbar shows "Google Doc ↗" only when a Doc is already linked (`desk.js:314`).
   - "Send to Google Doc as suggestions" says "This blog has no Google Doc to send to…" (`desk.js:874`).
   - `google-open` guards a run (`management.py:1926-1934`, `blog_runner.guard`), so a desk blog fails on the server as well.
   - The old Done card's "Open as a Google Doc" (`runner.js:1029`) has no desk equivalent, yet the desk spec's top bar lists "Google Doc" and `references/page-tools.md:49` still promises it.
5. **The Proofread panel describes the wrong tool.** `desk.js:813` uses `DESK_TOOLS[1][2]`, and index 1 is now Apply a voice (`desk.js:599`). Proofread therefore opens with "The draft rewritten in one of your voice guides, section by section. Its facts, quotes, links and shape are kept. Fix rewrites only the sentence…". The journey (`check-management.cjs:3385`) does not check this line.
6. **The library's upload starts a blog outside the desk.** The upload dialog's "Start an editable blog from this file" (`index.html`, `app.js:646` `as_blog`) makes a blog with no run and no desk (`management.py:943-961`). The toast is only "Source saved; attach it only to the blogs that need it." The blog surfaces later under Home's "Saved drafts", and "Continue editing" there opens the old manuscript editor (`runner.js:181`). This contradicts `docs/design/blog-workflows.md`: "Every new blog starts on the writing desk".
7. **A Google Doc already linked to an older run refuses with no way through.** "Read Google Doc" on the desk start (`desk.js:191-195`) calls `desk-create` with `article`, which raises "This blog has a step-by-step run. Open it there." (`desk.py:313`). The start then shows "…Your choices are kept here." with no link to that run.
8. **A long pasted draft is refused only after Start.** The paste field allows 1,000,000 characters (`desk.js:175`); the server takes 200,000 ("Use a draft up to 200,000 characters.", `desk.py:328`).

## Part A.2 Confusing or contradictory copy, and two names for one thing

1. **"Desk" means two things.** It is now a screen, but the server and the old editorial page still use it for the whole page:
   - `management.py` `failure()`: "The desk helper hit an unexpected problem. Reload the desk; saved work is kept, and you can continue in chat."
   - `Busy`: "Another desk operation is still running…"
   - `PROTOCOL_ERRORS`: "The editorial desk answers GET and POST requests only."
   - `app.js:126`: "Reopen the current desk link"; `app.js:161`: "The desk helper is not answering. Ask Blog Studio in chat to open the editorial desk again."
   - `app.js:384`: "This desk does not publish your blog."
   - `desk.py:1184`: "This request has fields the desk does not take."

   On the writing desk, "Reload the desk" reads as reloading the draft.
2. **"Polish" and "edit" lead to two tools.**
   - Home's "Edit or polish a draft" opens the desk (`runner.js:356`).
   - The Done card's "Polish or edit the draft" opens the manuscript editor (`runner.js:1049`). The editor is labelled "Improve a draft" (`runner.js:434`) and its steps are "Polish / Choose changes / Finish".
   - The Google page is still titled "Polish a document" (`runner.js:146`).
   - "Proofread" also means two things. The first pass "Tighten and proofread" (`desk.js:5`) is an assistant job; Finishing's "Proofread" is "checked at once with no assistant" (`desk.js:600`). The editor's "Polish writing" is "Grammar, clarity and natural wording" (`runner.js:450`).
3. **The Default voice hint is false for every new blog.** With the voice switch on, Settings says "A confirmed voice, chosen as Write as for every new blog unless you pick another." (`runner.js:200`). New blogs are desk blogs, which "write with its tone only: no default or pinned voice is applied" (`desk.py:270`). Only Interview me and chat runs use the default voice.
4. **The research ticks contradict themselves.**
   - Settings shows a "your documents" tick under "Research for new blogs from:", with the hint "Your documents are always read." (`runner.js:65`).
   - The server's rule is "None ticked is no research" (`blog_runner.py:101`).
   - The desk start ignores the documents tick (`desk.js:53`).

   The tick looks optional, does nothing for a desk blog, and does change chat runs.
5. **"Where new work stops" sits in Blog Studio's Settings** (`runner.js:72`). Its text: "Where a new deck, a new training or a blog run step by step in chat stops for you, in every studio. A blog on the writing desk has no stops." Its toast: "New work in every studio now starts at Balanced." For Blog Studio it does nothing on the page. Old runs still print "Balanced review ·" under About this blog (`runner.js:257`).
6. **Kind of post and style are two names for one thing.** With voices off, the screen is "Kinds of post", but:
   - the toolbar says "Create a style" (`runner.js:668`) and the card offers "Write a style guide" (`:653`);
   - the detail sheet offers "Edit this style guide", "Export style guide", "Retire this kind of post" and "All voices and styles" (`:793-796`);
   - learning one is "Style name" and "Build a provisional style" (`:782-785`);
   - the library says "Learn a style from these".

   The roles "Example of the kind of post" and "Example of a kind of writing (style sample)" (`index.html` upload purpose), and the filters "Examples of a kind of post" and "Style samples", are the duplicate the 2026-10-21 review named. They are still there.
7. **One saved profile has three names: voice guide, voice and voice profile.** The sidebar says "Voice guides" and "New voice guide". With the switch on, the Voices card's "Write a voice guide" opens a different editor (`sEditVoice`: "Edit voice guide", "Profile name", "Author rules (JSON)", `runner.js:919`). `sVoiceProfile` is titled "Voice profile", with "Retire this profile" beside "Edit this voice guide". Retiring a guide says "blogs that write as it keep it" (`runner.js:742`), and "Write as" is hidden by default.
8. **The All blogs details still speak the old flow.** Built by `management.py:1137-1245` and shown by `app.js:360-395`: "Requested stop: draft", "Continue in chat", "Keep the requested stopping point (draft) unless I explicitly change it", "No manuscript is saved yet. Continue in chat to plan the requested writing step.", and "Open writing run" (it opens the desk for a desk blog). The empty board says "…or start a blog in chat"; the Review findings inbox says "Run a review in chat to collect findings."
9. **The same tool has a name on the desk and another in Tools or the editor:**
   - History (`desk.js:381`) vs "Saved manuscript revisions" (`runner.js:552`) and "Decisions and history" on a run;
   - "Headline and opening" vs "Improve a title or opening";
   - "Feedback without a rewrite" vs "Review argument and structure" and the old "Review a draft";
   - "Check facts against sources" vs "Check facts";
   - Repurpose: on the desk "each copy you keep becomes a new blog" (`desk.js:846`); in Tools "Save named copy… Saved separately from the blog" (`runner.js:952, 990`).
10. **Some leftover wording names things that don't exist.** `blog_runner.py:564` "Choose Run this blog on the page." Restore's "It stays stopped until you resume it." Status calls every blog, desk blogs included, "Writing activity → Every run" (`runner.js:186`). Home's filled button for a stopped desk start reads "Review <title>" (`runner.js:181`).
11. **The start's order hides what step 3 decides.** Step 2 shows research and Length according to `have` (`desk.js:87-88`), but `have` is chosen in step 3. Start from New blog (topic), tick research, then pick "A draft" at step 3: the research is dropped with only "A draft you bring is edited as it is, without research." (`desk.js:186`). Start from "Edit or polish a draft" and switch to "A topic": Length was never offered. The desk spec puts "What do you have?" before "Sources and settings"; the page and `blog-workflows.md` put it after.
12. **The interview names the wrong place to resume.** It says "Pause by closing and resume from this article's tools." (`runner.js:969`). Resume is actually Blogs → "Resume interview" (`runner.js:185`), as `page-tools.md` says.

## Part A.4 Desk vs the rest of Blog Studio

1. **Desk blogs never reach the team library.** An old run's Finish keeps its draft (`blog_runner.keep_finished`; the sheet says "Its draft is kept in the team library as a reference and an example of its kind of post", `runner.js:308`). The desk has no Finish, and Mark as published keeps nothing. Two lines no longer hold for new posts: the library's lede "Finished blogs, files, links and Google Docs…" (`app.js:48`) and `docs/capabilities.md:45` "Every finished blog … | Finish". The next blog cannot pick them as examples, and the library stops growing.
2. **Phase 1 recovery and Phase 2 cost exist only on old runs.** Old runs have "Continue without research", "Try again with more time", "Open Status", "What the research check objected to", "Round n of 3", and "N steps left · Next stop · So far $" (`sAhead`, `sRound`, `sResearchStop`). The desk shows one problem line, Retry, and a minutes clock (`desk.js:268-291`). There is no spend and no grouped objections.
3. **Research is invisible on the desk.**
   - The Phase 3 research account (`runner.js:265` `sResearchAccount`: brief, independent check, gaps, questions, report, evidence) has no desk counterpart.
   - The sources aside says "No sources were given for this draft. Rewrites keep to what the draft already says." (`desk.js:407`) even when research ran and every rewrite reads it (`desk_jobs.py:321`, `_research_extra`).
   - The desk start also brings back the research-plan job (`desk_jobs.py:915`) that Phase 3 meant to replace with scope fields.
4. **No Google Doc and no team driver on the desk** (A.1 1 and 4). A run shows "X · driving on another computer" with Take or Hand over; the desk shows neither who drives it nor any control.
5. **One finished old blog has two editors.** Its Done card offers both "Open on the desk" and "Polish or edit the draft" (`runner.js:1046-1049`). Once the blog is on the desk, editor writes are refused (`manuscript_editor.py:97`). Home's "Saved drafts" opens the editor first, with "Open on the desk" only as a toolbar button (`runner.js:433`).
6. **Tools versus Finishing.** Runs and the editor keep the Tools sheet: Repurpose as named variants, Saved manuscript revisions, Pre-publish, Improve clarity, Improve a title or opening, Compare Google and local text, Saved channel copies, Interview me and Delete. The desk has Finishing: overlapping tools under other names that behave differently (A.2 9). The desk has no Tools, no Delete and no saved channel copies. Delete is only on Home and Blogs rows.
7. **A desk blog never finishes.** Old runs move to "Finished drafts"; a desk blog stays in "In progress", marked "On the desk", until "Mark as published" (`blog_runner.catalog`, `blog_runner.py:2751`). Home's In progress grows with every blog.
8. **A desk blog's kind of post and tone are fixed after Start.** The aside shows "Kind of post: X" and "Tone: Y" read-only (`desk.js:409-410`). An old run could change its voice with "Change the voice".
9. **The spec and docs disagree with the page:**
   - the start's order (A.2 11);
   - the top bar's "Google Doc" (A.1 4);
   - `blog-workflows.md` "Every new blog starts on the writing desk" (A.1 6);
   - `page-tools.md:49` "Open as a Google Doc: on Done", which is true only for old runs.


## Part A.3 Cleanup

Paths: `B/` = `studios/blog/skills/blog-studio/`, `M/` = `B/assets/management/`, `T/` = `studios/blog/tests/`, `CI/` = `studios/blog/scripts/ci/`. Callers checked by grep over the page scripts, `index.html`, server and tests.

**Key fact for the whole section:** chat still starts new step-by-step runs. `run create` (B/scripts/blog_runner.py:3412, 3519-3546; B/references/guided-runs.md:17-60) has no desk equivalent, and the CLI has no desk group. So the pipeline, review levels, claims map, research stop and gates are not used only by older blogs. Chat uses them for new work too. Most of the pipeline can't go until that changes (see Needs a decision 1).

### Safe to delete now

Ranked by confusion or upkeep cost.

1. **"Start an editable blog from this file" in the library's Upload one file dialog.** This is the one way left on the page to start a blog off the desk.
   - Where: M/index.html:43 (`upload-blog`), M/app.js:646 (`as_blog`), reached from runner.js:1100 ("…or start an editable blog from it").
   - It creates an `existing` manuscript blog for the manuscript editor (B/scripts/management.py:943-960), not a desk blog. It contradicts "Every new blog starts on the writing desk".
   - Remove the tick, or send it to the desk start with "Use this blog's saved draft".
   - Once the polish intake (item 2) is gone too, the server's `as_blog` branch has no caller: management.py:872, 906-912, 943-960.
   - Docs that describe the tick: studios/blog/docs/editorial-desk.md:64, studios/blog/docs/runner.md:362-363.
2. **The old Polish a document and Google Doc intake screens.**
   - Functions: `sPolishIntake` runner.js:359-400 ("Polish a document", "Choose your document", "Open for polishing") and `sGooglePage` :142-180 ("Open your manuscript", "Read Google Doc"). Their helpers `sGoogleResult` :133-141 and `sGoogleButton` :125-127 (no caller since cc5cd88).
   - Screens: `google`, `draft` and `polish` in the router (runner.js:105, 114-116) and the poll skip list (:315).
   - No button reaches them since bc3909a and cc5cd88; only a typed `?screen=polish|draft|google` does. Send those addresses to `desk-start`, as `screen=new` already is (:104).
   - Keep `sGooglePreview` :128: the desk start uses it (desk.js:197).
   - Journeys that test only these screens: CI/check-management.cjs:459-485 (rest of `taskJourneys`), `googleReopening` :486-528, `googleIntake` :529-586 (including the `sGoogleButton` checks at :566-580), and the `sRoute('polish')` navigation at :289-290. Move the "already linked Doc reopens" case to the desk start (`sDeskReadGoogle` desk.js:189-197) before deleting.
3. **The page's `run-create` route.**
   - No page script has called it since cc5cd88. Chat uses the CLI's `create()`, not this route.
   - Delete: B/scripts/management.py:2154-2155 (voice-switch check) and :2272. In blog_runner.py: `dispatch` `create` :3162-3177, the `.blog-runs/creations` operation ledger, and the form-only fields `review_level`, `review_seen` and `review_default` (:1237-1239, :1245-1253, :1498-1501, :1527-1529). Those fields came only from the removed "Where this run stops" chip; the CLI never sends them.
   - Tests that go with it: T/test_blog_runner.py `test_a_blog_keeps_the_level_its_form_chose`, `test_the_default_is_written_only_with_the_chip_and_refused_when_stale`, `test_an_unreadable_shared_file_still_starts_a_blog_at_its_level` (1303-1360), `test_read_only_hub_cannot_start_page_work` :692-695, `test_authenticated_http_pipeline_completes_all_gates` :710-744 (switch it to the CLI `create`), runner `dispatch('create')` :476-477; T/test_voice_switch.py:285-287.
   - Fixture mocks of `/api/run-create` in CI/check-management.cjs:451, 1638, 2697 are dead. The "never called" asserts at :561 and :3101 can stay.
4. **The private `stop` writing default.**
   - Where: `DEFAULTS['stop']='package'` (blog_runner.py:103), checked on save at :499-500, sent back by Settings because `held` copies `defaults`.
   - Only the removed wizard read it (`defaults.stop`). `create()` uses `data.get('stop','package')` (:1290). It does nothing now.
   - Test fixtures carry it: CI/check-management.cjs:442, 530.
5. **The `source-keep` route** (management.py:2001-2002). Its page caller (the files screen's Keep tick) went in cc5cd88.
   - Keep the function `source_keep` (management.py:795): desk.py:949 uses it.
   - Tests that call the route: T/test_desk_start.py:1023-1028 and T/test_team_library.py:1934, 1963 (`source_keep` direct is enough).
6. **Page functions nothing calls.**
   - `sBrandNotice` runner.js:325-329: no caller since #97 (1937c01). Its brand poll on Home (:322) now redraws Home for nothing.
   - `renderRun` runner.js:311: only CI:1332 calls it.
   - app.js `views.runs` ("Writing runs", "Start a blog, review each stage…") and the `view==='runs'` branch app.js:230. `sLegacy` admits only board, inbox, library and memory (runner.js:313).
   - `BLOG_MODES` descriptions (runner.js:5, third field), left from the Home cards. Only the label is read (:183).
7. **blog.css classes no markup uses** (none appear anywhere in the repo): `.studio-hidden-controls` :3, `.blog-search` :4, `.stage-link` :8-9, `.file-actions` :9, `.review-compare` :10, `.empty-invite` and `.blog-facts` :14, `.manuscript-original` :54, `.editor-suggestions` :55, `.finish-summary` :67, `.view-library` :125.
8. **Stale comments that name removed screens.**
   - management.py:924 ("as on the files screen") and :826 ("this computer's start form").
   - blog_runner.py:1245-1246 ("the level its form chose… The form's chip"), :2843 ("the wizard still opens"), :396 ("a start form says").
   - T/test_blog_runner.py:2198 ("the wizard opens…").

### Still needed for older blogs (and for chat runs)

Ranked by what a person would lose if it were deleted.

1. **Run, gate and Done screens and the angles gate** (runner.js `sRun` :252, `sReadGate` :263, `sGate` :278, `sConfirm`, `sChanges`, `runAction` :308-310, `sNoneOfThese` :1272, `sAngles` :1275). The server side: `blog_runner.dispatch` approve, changes, note, develop, adopt, retry, pause, start, `skip-research` and `apply-review` (blog_runner.py:3193-3300).
2. **The manuscript editor**: `editor-*` routes and B/scripts/manuscript_editor.py. Its checks create a `review`/`revise` run (manuscript_editor.py:341-360). Reached from Home's Saved drafts and from Blogs' "Continue editing" on ordinary blogs (runner.js:181, 185).
3. **The pipeline**: `STAGES` (research-plan, research, claims-map, outline, draft, review, package: blog_runner.py:37+), `claims_map.py`, `synthesis_research.py` (the desk also uses it), and the stage modules under B/references/modules/ (blog-research-plan, blog-claims-map, blog-argument-outline, blog-write, blog-fact-check…).
   - The desk also uses `blog_runner.inputs`, `STAGES`, `REFERENCES`, `GUIDES`, `LENGTHS`, `WRITING_NOTES`, `GAPS_OPEN`, `house_guide`, `shared_guidance`, `library_picks` and `engine`. Those are shared helpers now and are never deletable with the pipeline.
4. **Review levels in a run**: `review_policy` snapshot and `automatic()` (blog_runner.py:531, 970-977, 1032, 1495-1505). `core/studio_core/review_policy.py` and `stops.py` (Part B: also Presentation Studio and Training Studio). Root tests/test_review_policy.py blog cases :50-60, 122-150, 198-250.
5. **Phases #85–#88 on runs**:
   - #85: steps left and next stop (`sAhead` runner.js:69), Try again with more time.
   - #86: the research stop view (core `research_view.py`).
   - #87: Apply the review's findings (runner.js:281) and the Done card's Pre-publish check, Repurpose and Open as a Google Doc (runner.js:1026-1040 → `google-open` management.py:1926-1935 → `google_handoff.open_as_doc`).
   - #88: brand guidance and `--voice-profile`.
6. **Announcement writing #90 checks that only runs perform**: `reader_facing_notes` (text_checks.py:243; used at blog_runner.py:2117, 2980), `carried_over` from-example (text_checks.py:141; blog_runner.py:1901), and the handoff check. Keep them, and port them to the desk (Needs a decision 5).
7. **Tools sheet per-blog tasks** (runner.js:539-560): Repurpose this blog, Pre-publish check, Improve a title or opening, Improve clarity and citation readiness, Saved manuscript revisions, Compare Google and local text. Only old runs and the editor open them; Finishing does most of the same on the desk.
8. **Legacy research** (`deep_research.py`, studio.py:1058, 1348; modules/blog-legacy-research.md). This predates the desk.
9. **Tests for the above**: T/test_blog_runner.py (most of it), test_run_recovery.py, test_synthesis_integration.py, test_manuscript_editor.py, test_google_handoff.py, and the run, gate, editor and Done journeys in CI/check-management.cjs.

### Needs a decision

Ranked by what a person loses.

1. **Chat writes outside the desk.** Chat `run create` makes a gated run, while the page makes a desk blog. The same person gets two products depending on where they start.
   - Until chat gets a desk create (or `run create` makes desk blogs), items 1-5 of "Still needed" stay live.
   - After that switch they become older-blogs-only, and can go once older runs can be brought to the desk (item 7).
   - Docs that describe chat starting gated runs: B/references/guided-runs.md and B/references/entry-flows.md ("Outline only", "Interview me", "Discover an idea"), studios/blog/docs/runner.md:296-340.
2. **Settings → Where new work stops on Blog Studio's page** (runner.js:72: "Where a new deck, a new training or a blog run step by step in chat stops for you… A blog on the writing desk has no stops").
   - On Blog's own page it governs nothing on the page, only chat runs and the other two studios.
   - Route `review-level` (management.py:1917) and test `test_review_level_route_saves_and_refuses` (T/test_blog_runner.py:1364).
   - Drop it from Blog's Settings and leave it in Shared settings, at least until the other studios have desks (Part B).
3. **The brand skill no longer reaches page blogs.**
   - desk.py, desk_jobs.py, desk_finish.py and desk.js never read a brand. Only `run create` snapshots one (blog_runner.py:1523-1525) and hands it to the worker (:710-711).
   - Blog's Settings still has Brand settings (runner.js:205), and Status and Home poll the brand.
   - Either wire the brand into the desk's guidance or say the brand applies to chat runs only.
4. **Author (shared `person.name`) does nothing for desk blogs.** desk.py:340 and :464 create with `author=None`; only `run create` applies it (blog_runner.py:1209). Settings' "Author (optional)" (runner.js:200) implies otherwise.
5. **#90 safeguards the desk lacks.** Desk drafts are never checked for source IDs or editorial notes in the prose, or for passages carried over from an example: `desk_finish.proofread` uses `lint` only (desk_finish.py:509-520). Port these checks to Proofread, not delete.
6. **Tools sheet vs Finishing.**
   - Duplicates: Repurpose ↔ Before publishing → Repurpose; Pre-publish check ↔ Before publishing; Improve a title or opening ↔ Headline and opening; Saved manuscript revisions ↔ History.
   - "Improve clarity and citation readiness" (GEO) has no desk equivalent.
   - Two Google handoffs: `google-open` on the Done card vs `desk-google-plan`/`desk-google-send` on the desk.
   - Choose whether GEO joins Finishing, then retire the per-blog Tools tasks along with the old runs.
7. **Only finished old runs can come to the desk.** `desk_open` requires complete or finished (blog_runner.py:2375-2379). An old run waiting at a gate, or a manuscript-editor blog that never finished, can't come to the desk. That keeps every gate screen alive indefinitely.
   - Related: Blogs' "Continue editing" on an ordinary saved draft opens the manuscript editor (runner.js:185), while its details' Open writing run brings the same draft to the desk start (runner.js:207-216).
   - Pick one; offering the desk for any run with a DRAFT.md would let the gate code retire.
8. **Docs.**
   - docs/design/blog-workflows.md "Interface contract" (≈lines 24-75) states old-run gate and editor rules as current ("Ideas have one primary 'Develop an idea' action", "New-writing gates retain their decisions"). Move them under "Blogs started before the desk".
   - The validation and record docs in studios/blog/docs/ describe pre-desk flows. epic-27-validation.md, startup-validation.md and google-gcloud-validation.md are linked from nowhere. Archive them, or mark them historical.


## Part B. Marketing Studio home and shared setup

Canonical files: `core/studio_core/setup_web/{index.html,app.js,home.css}` (Marketing Studio's
`marketing_studio/web/*` are symlinks to them) and `ui-kit/style.css` (symlinked as every
studio's `style.css`). `studios/*/scripts/studio_core` are symlinks to `core/studio_core`, so
there is one copy of every core helper. The same setup page is served inside each studio as
its first-run "Welcome to <Studio>" (`core/studio_core/onboarding.py:89-99`, product name
substituted into the HTML); Blog Studio uses it (`start_studio.py:82-84`, `management.py:2824`).
Below, bare `index.html`, `app.js` and `home.css` mean `core/studio_core/setup_web/…`;
`runner.js` means Blog Studio's `assets/management/runner.js`.

### B.1 Layout rules (golden-gate.md "Layout rules")

Ranked by what a person loses.

1. **Setup: one step, three titles, two names.** In first-run setup the step shows the
   `.workflow-step` "Your workspace" (`index.html:44`, `app.js:36`), the large title from
   `labels[step]` (`app.js:92`) and the card title "Where your work lives" (`index.html:69`);
   step 1 shows "You and your assistant" three times (`index.html:44,46`, `app.js:92`) plus
   "Step 1 of 3" (`app.js:94`). Rule: one lede saying what the screen is for, one heading per card.
2. **Headings inside cards use the sheet heading.** `h4.sheet-part` "Models for your work",
   "Review level", "Where is your brand skill?", "Delivery and previews" sit inside `.card`s
   (`index.html:55,64,80,94`), and each profile `paper` card gets `h5.sheet-part`
   (`app.js:268`); This computer uses `h4.row-title` in a card (`app.js:493`). Rule: one heading
   level per card (`.card-title`), `.sheet-part` only inside a sheet. Either split these into
   cards or name a shared in-card subheading.
3. **The settings page has two saves.** "Save settings" ends the form (`index.html:109`), then
   a second card, Studio installations, follows with its own "Save installation folders"
   (`index.html:111`). Research sites asks "Save settings to keep the list" (`index.html:106`)
   for a list edited live. A person who changes a folder and a setting must save twice. Rule:
   a form's submit sits at its end; setup comes after what needs the person.
4. **Review level is filed under "You and your assistant"** (`index.html:64`), not with the
   work it governs; with desks it governs only Presentation Studio and Training Studio (B.2).
5. **Ledes.** Home: "Your settings are shared. Each studio has its own space to work."
   (`index.html:30`) — two sentences, says nothing about the screen (launch a studio). This
   computer: "Check the tools available to your studios. Each studio checks sign-in when you
   use it." (`index.html:114`). Setup: "Set up once. Your studios will start with these
   choices." (`app.js:93`). Rule: one sentence saying what the screen is for.
6. **This computer's only action is filled and below an empty list** ("Run a check to see what
   is installed." then the filled "Check computer", `index.html:115`), not in the toolbar.
   Rule: the screen's one filled primary goes in the toolbar after the title.
7. **Home has three filled buttons** ("Open Blog Studio", "Open Presentation Studio", "Open
   Training Studio", `app.js:355`) and no toolbar primary; acceptable as one per launch card,
   but a "Connect" (`app.js:340`) that the person needs sits inside the card below status
   rather than first. Rule order: what needs the person first.
8. **The page stylesheet draws shared controls.** `home.css:28-41` `.studio-icon` re-draws the
   rounded tinted tile that ui-kit already has as `.studio-symbol` (`ui-kit/style.css:369`);
   `home.css:65-76` `.studio-status::before` draws a status dot instead of `.state`/`.bead`
   (which `app.js:71-75` already uses for the workspace line, so one card shows two dot styles);
   `home.css:311-318` `.site-row` draws a ruled list instead of `.table`. Rule: a page
   stylesheet sizes and places, never draws.
9. **Spacing off the rule.** `.studio-list` gap `1rem` (`home.css:18`, rule 1.1rem between
   cards); `.setup-part > * + *`, `#model-profiles`, `.setup-more`, `#brand-choices`,
   `.profile-card`, `.profile-explicit` use `0.8rem` (`home.css:157-162,205-208`; rule 0.6rem
   inside a field group); `.profile-cards` gap `0.8rem` (`home.css:197`).
10. Fine as is: shell meets edges; glass only on sidebar, toolbar and toasts (`app.js:45`);
    "Back to <Studio>" only in a studio's standalone setup, which has no sidebar
    (`app.js:90`); 44px disclosure (`home.css:166`); field grid reflows at 40rem.

### B.2 Shared settings only the old Blog flow reads (and what they mean once all use desks)

1. **Review level (`review.level`)** — `index.html:64-66`, written by `app.js:411`, checked by
   `review_policy.py`, `preferences.py:52,119,170`, `studios_config.py:105-112`.
   Readers: Presentation Studio (`runner/engine.py`, `stages.py`, `decks.py`, `setup.py`,
   `page.py`, desk `app.js`) and Training Studio (`runner/engine.py`, `pipeline.py`,
   `reviews.py`, `setup.py`, `page.py`, desk `app.js`) for every new run. Blog Studio: only
   step-by-step runs started in chat (`blog_runner.py:531,1237-1249,1498`) and Settings' "Where
   new work stops" card (`runner.js:72`, route `review-level` `management.py:1918`,
   `blog_runner.py:1122`). The desk (`desk*.py`, `desk.js`) never reads it. Once all three
   studios use desks with no stops, it means nothing for new work and only pins old runs (each
   run keeps its own `review_policy`). Keep the stored key and `review_policy.level()` for
   old runs; remove the shared control, `review_policy.change`, `STALE`, the Settings cards
   and the start-form stops cards when the last studio moves.
2. **Share changes "After each decision / When I ask" (`share`)** — `index.html:75`. Still
   read (Blog `team_workspace.py:48`, Training `gitstate.py:158`). On Blog's desk a "decision"
   is now a settled job or Finishing Apply; autosaves are not decisions and wait for the next
   one (`team_workspace.py:335`, `desk_jobs.py:1557-1580`). The setting works but its word is
   the gate vocabulary; with desks it needs a new meaning ("after each rewrite or apply").
3. **Default brand and variant (`brand.*`)** — `index.html:79-90`: "Choose the brand new work
   starts with. You can change it for each blog, presentation, or training." No desk file
   mentions a brand (`grep brand desk*.py desk.js desk-*.md` is empty); only the old run
   snapshot reads it (`blog_runner.py:1515-1525`, `711`, `1056`). New blogs get no brand, and
   no per-blog choice exists. Either the desk adopts the brand (the review's
   `--voice-profile`/naming rules) or the copy drops "each blog".
4. **Models by task (`models.*`)** — every Blog desk job routes as step `draft`
   (`tool_jobs.py:220`) so it always uses Main; Quick and Complex never apply to Blog. The hint
   (`index.html:58`) lists only deck tasks for Quick and Complex, which is accurate but leaves
   Blog people tuning profiles that do nothing for them. A shared desk would want selection
   edits on Quick.
5. **Deliver as (`output`) and Slide previews (`render.previews`)** — deck-only
   (Presentation `settings.py:383,415`, Training `setup.py:225`, `settings.py:362`); shown in
   Blog Studio's own first-run setup (step 3 "Brand and delivery") where they do nothing.
   Not old-flow, but irrelevant on the Blog path.

### B.3 Home and onboarding copy that describes Blog's old flow

1. **Review level copy** `index.html:65-66`: "When should work stop for your review?"
   "Balanced — direction and finished work", "Automatic draft — finished work only", "Step by
   step — every stage", "Balanced brings research and the planned direction together for one
   review, then shows the finished work… New work saves this choice; existing runs keep their
   review level." For a new blog nothing stops and nothing is saved. Blog Studio's own Settings
   already says "A blog on the writing desk has no stops" (`runner.js:72`) and
   `docs/shared-setup.md:120` says it, but the shared page does not — and Blog Studio's
   first-run setup asks this question of a Blog-only person (step 1). Highest loss: a new
   person is asked to pick stops that will never happen.
2. **Blog Studio's card on home**: "Shape your ideas into blogs in your voice."
   (`marketing_studio/catalog.py:6`). Voice tools are off by default (`features.voice`); new
   blogs are written with Tone, and the desk's way in is "a topic, notes or a draft". README
   already says "One writing desk…" (`README.md:32`).
3. **"You can change it for each blog"** (brand, `index.html:79`) — see B.2.3; false for the desk.
4. **"After each decision"** (`index.html:75`) — gate vocabulary; see B.2.2.
5. **Three names for one setting**: "Review level" / "When should work stop for your review?"
   (`index.html:64-65`), "Where new work stops" (Blog `runner.js:72`, refusal
   `review_policy.py:24` "Another studio changed where new work stops").
6. **docs/shared-setup.md** (the setup page's doc): `:137-140` "A Blog Studio run includes
   research with the outline, and the writing, independent review and requested handoff at the
   final stop" (chat runs only, not said); `:44` "author voice … selected when starting work"
   (hidden by default); `:150` "Marketing Studio's onboarding page keeps its own control"
   (right, but it is the control that lacks the desk caveat).
7. Home itself (`index.html:29-40`) and the sidebar foot carry no old-flow copy.

### B.4 Dead core helpers

Scan: every top-level function, class and constant in `core/studio_core/*.py` and
`marketing_studio/*.py`, counted across tracked files (symlinked copies excluded, upstream
references excluded). No core *function* is dead; nothing in `marketing_studio/*.py` is dead.

Safe to delete now (no production reader):
1. `deck_flow.CHECKPOINTS` (`core/studio_core/deck_flow.py:47`) — no reader anywhere; `PAUSES`
   replaced it.
2. `research_view.REFRESH` (`core/studio_core/research_view.py:107`, "Bring the evidence up to
   date") — no reader; `refresh_words` builds its own words.
3. `deck_flow.DESIGN_SESSION` (`:76`) and `deck_flow.SHARED_INPUTS` (`:80`) — read only by the
   test fixtures `studios/{presentation,training}/tests/deck_contract.py` and
   `tests/test_deck_contract.py`. Keep only if those contract tests are wanted.

Core helpers now used by Blog Studio's old flow only (inside Blog), but still live because
Presentation Studio and Training Studio call them — not dead until those studios move to desks:
- `review_policy` (`ahead`, `automatic`, `receipt`, `change`, `capture`, `held`, `STALE`):
  Blog reads it only in `blog_runner.py` (old runs, chat runs, Settings' Where new work stops).
  The `product == 'blog'` branch (`review_policy.py:126-127`) and the docstring line about a
  blog under Balanced (`:111-112`) serve only old and chat Blog runs: **still needed for older
  blogs**.
- `stops.redone`, `stops.took`, `stops.cost` and `research_view.price`: Blog calls them only
  from `blog_runner.py:917,1154,2302-2306` (Ask for changes pricing, "So far" spend on a run).
  The desk shows no spend or price. Shared with both deck studios.
- `deck_flow` reaches Blog only through `review_policy`.

ui-kit (`ui-kit/style.css`): no rule is Blog-old-flow-only. The gate, bead, stops-line,
ahead-line and review-bundle styles (`:732-866`, `:1510-1600`, `:2154-2192`, `:2747-2758`)
are used by Presentation Studio and Training Studio as well as Blog's `runner.js`; they become
dead only when those studios' gates go. `.workflow-steps` (`:2460`) is used by the setup
progress (`index.html:44`) and Blog's runner. `.dialog-header`, `.dialog-form`,
`.dialog-content` (`:2576-2607`) are used only by Blog's `index.html` dialogs (Blog details,
"Bring in your work" upload, shared memory, Import old blogs; `index.html:41-77`); if Part A
finds those dialogs unreachable, these rules go with them. `.looks .look-choice` (`:1764`) has no user in any page script: likely dead (deck studios).

`tests.test_ui_consistency` passes (6 tests) at cc53056 with a disposable HOME.


## Part C. Sharing the desk

Paths: `B/` = `studios/blog/skills/blog-studio/`. Ranked by what a person loses if the part is copied into each studio and then drifts. The first risk is losing text, then losing a running job, then two studios behaving differently.

### What blocks or shapes any sharing

1. **Name clash.** Presentation Studio and Training Studio already use "desk" for their page and server: `scripts/desk/` in both, and Training's `scripts/desk.py` is its HTTP page. So a `studio_core/desk.py` would be read as a page module. Use another name for the shared module, such as `studio_core/draft_desk.py` or `writing_desk.py`, and say "draft desk" in code.
2. **Storage helpers.** Every desk module calls Blog's own `studio.py`: `lock_held`, `locked`, `item`, `inside`, `atomic`, `read_json`, `write_json`, `digest`, `now`, `persist`, `metadata_path`, `save_artifact`, `article_record`, `new_id`, `style_pin` and `style_check`. Those helpers assume the `articles/<id>/session.json` layout and `.blog-runs/`. Presentation and Training have their own `workspace.py` (`write_atomic`, `locked`). Core needs a small store interface the studio passes in: the item folder, lock held, atomic write, read and write JSON, digest, now and the export file name. Every module below then takes that store instead of importing `studio`.
3. **Two job models.** Blog's worker (`blog_worker.generate`) sends a payload and guidance and gets schema-checked JSON back on stdout (`--output-schema` or `--json-schema`, `web=False`). Presentation and Training run file-writing agents in a job folder with a worker tools server (`runner/agents.py` `Job`, `Outcome`, `Slots`), and run some of them in parallel. A shared job queue needs a JSON-result mode in those two studios' `agents.py`, or an adapter that reads a `result.json` the agent writes.
4. **Two page dialects.** `desk.js` calls about 30 helpers from Blog's `runner.js` and `app.js`: `sNode`, `sButton`, `sCard`, `sField`, `sCheck`, `sChoice`, `sFrame`, `sPage`, `sOpenSheet`, `sCloseSheet`, `sToast`, `sBead`, `sWorkflowSteps`, `sPickCard`, `sRoute`, `sNarrow`, `sFilesCard`, `sGooglePreview`, `sLengthSelect`, `sSitePicker`, `sSharedSites`, `api`, `notice`, `busy`, `disclosure`, plus the globals `access`, `studio` and `token`.
   - Presentation's and Training's `app.js` share one other helper set. These are byte-identical in both: `make`, `button`, `card`, `choice`, `segmented`, `toast`, `bead`, `state`, `chip` and `narrow`. These have drifted: `field`, `openSheet`, `closeSheet` and `pickCard`.
   - `ui-kit/` holds only `markdown.js` and `style.css`.
   - A shared `ui-kit/draft-desk.js` would need its own small DOM helpers and an adapter object passed in by the studio (`api`, `toast`, `openSheet`, `closeSheet`, `notice`, `busy`, `canEdit`, `route`, `words`).

### C.1 Desk record and versions (`B/scripts/desk.py`): mostly shareable

Losing this costs text, so share it first.

**Share:**
- Splitting and joining: `split`, `join`, `has_heading`, `outline_from`, `_title_line`, `_id`, `_tidy` and the `FENCE`, `TITLE`, `HEADING`, `ANY_HEADING` and `ITEM` patterns.
- Reading and writing one part: `_part`, `text_of`, `_set`, `checked_text`.
- The per-part stale check: `checked` with the `changed` map, so "a rewrite landing in one section never refuses typing in another".
- `save`.
- Versions: `keep`, `versions`, `counts`, `restore` (`KEEP=20`, one version per editing session).
- Removed sections: `removed`, `_keep_removed`, `unremove`.
- `outline_save` and `reimport`, which matches sections by heading so ids and History follow the text.
- The middle of `_write`: revision +1, the `changed` map, writing `draft.json`, rewriting the export file, and keeping text changed outside the desk in `history/` first.
- The idempotent create ledger pattern in `_create`, keyed by operation and fingerprint.
- The route-table pattern of `ROUTES` and `dispatch`.

**Blog-specific:**
- `create`, `_start`, `_attach`, `_citable` and `_research_choice`. They build a blog record from old-run fields (`SimpleNamespace(... mode='first-draft', stop='review', research='supplied-only')`), and handle source roles, team library picks, kind-of-post pins, `voice` set to tone only and `flow:'desk'`.
- `open_run`, which uses `blog_runner.load` and `survey`.
- `keep_in_library` and `add_sources`, which call `management.source_keep`.
- The `DRAFT.md`, `session.json`, `artifact_hashes` and `record['stage']='draft'` side of `_write`, and `.active-article.json`.
- The `chat` and `google` version sources.
- `UNSHARED` and the `team_workspace.guard` call in `dispatch`.
- Every message says "blog": "Choose a blog on the desk.", "Give the blog a title.", `ON_DESK`. Take the product word as a parameter.

**Fit:**
- Training: each level's `document.md`, `product-brief.md` or `competitive-brief.md`, `blueprint.md`, `scenarios/*.md` and `yoodli/*.md` are Markdown with `##` sections. `split` and `join` fit as they are.
- Presentation: `outline.md` and `outline.json` hold sections of slides. Make core "parts with an id, heading, brief and text, and versions", with Markdown splitting as one codec and an outline-JSON codec (slide = part) for decks.

### C.2 Job kinds and the surgical-section rule (`B/scripts/desk_jobs.py`, `B/references/modules/desk-edit.md`): rule and mechanics shareable, writing context not

**Share:**
- The rule text `desk-edit.md`: change only what the note requires and keep everything else word for word. Only the opening line says "blog draft".
- `ACTIONS`: rephrase, shorten, expand and fix.
- `REVISE_ONE` and the `WHOLE` JSON contract.
- `_request`, which fences the author's words as an instruction rather than document data. Its text says "through Blog Studio"; take the product as a parameter.
- The basis check: `fingerprint`, `_sections_basis` and `STALE` in `_apply`.
- Reading results: `_clean`, `_no_heading`, `_section_texts`.
- Placing a selection: the start offset, the single-occurrence fallback, and keeping the surrounding whitespace.
- `_merge_gaps`.
- The whole-draft chain: `_chain_path`, `_chain_note`, `_next`, `_queue_next`. Each section is revised in turn, a failed one is reported, and Stop ends the chain.
- One job per item: `_busy` and `busy`.
- The per-item job index: `_index`, `_indexed`, `INDEXED`.
- `stop`, `settle`, `ended`, `_row`.
- The start chain: `_queue_step`, `_advance`, `begin`, `stalled`, `retry`, `expected_minutes` (a timing history of 20 runs per step).
- The angles store (`_angles_path`, `forget_angles`, `prune_angles`), used for options offered before the item exists.

**Blog-specific:**
- `_context`: `styles.pinned`, `blog_runner.inputs` and `blog_runner.shared_guidance`, which bring in the house guide, the kind of post, tone and `LENGTHS`.
- The prompt texts `WRITE_AGAIN`, `TIGHTEN`, `RESHAPE` and `RETURN`. `RETURN` is `blog_runner.WRITING_NOTES`.
- The writing guides `desk-write.md` and `blog-write.md`.
- Research: `research_job`, `research_run`, `_land_research`. They use Blog's research path; `research_contract` and `research_sites` are already in core.
- Outlines and drafts: `_apply_outline` and `_apply_draft`, and the outline JSON prompts.
- The angle fields: headline, point, audience.
- `blog_runner.engine(root).wake`.
- `view()`, which reads `editorial.doc_link`, `google_ready`, `publication`, `style_name` and `expected` (from `session.json`).

**Notes:**
- In production the rule is enforced by the prompt only. `desk_finish.changes_facts` and `changes_structure` exist but section rewrites and selections don't run them. A shared core could run that check on every section rewrite. That matters most in Presentation Studio: its `steps/outline.py` `verbatim` already enforces keeping words in code, and its "patch" step with marked slides is the nearest thing to a section note today.
- In Training Studio the same rule would replace "Ask for changes", which today rewrites a whole level.

### C.3 Finishing preview and apply (`B/scripts/desk_finish.py`): mechanics shareable, tools half and half

**Share:**
- The proposal store: `keep`, `_latest`, `_prune`, `read`, `sets`, `forget`, `summary`, `present`. Proposals are kept on this computer, not in the item folder, so a team workspace records only what Apply writes.
- `apply`. It refuses a part that is stale or has a job under way, leaves the rest open after Apply all (`left`), skips the other alternatives in a group, and keeps a `finishing` version first.
- `skip`.
- The settle frame: strict JSON with fences allowed, then `READERS`.
- The fact and shape guards: `changes_facts`, `_names`, `_named`, `changes_structure`, `_shape`, `_flags`.
- The row helpers `_rows` and `_located`.
- The tool prompts are close to generic: `HUMANIZE` with `LEVELS`, `FACTS`, `FEEDBACK` and `VOICE`, each with its JSON shape. `HEADLINE` speaks of a "post".
- `google_changes` (paragraph alignment against a Doc baseline) is generic code.

**Blog-specific:**
- `request()`. It reads `manuscript_editor.CHECKS`, `blog_runner.STAGES['review']` and the Blog guides `modules/blog-humanize.md`, `modules/blog-fact-check.md`, `review/evidence.md`, `review/shape.md` and `headline-lab.md`.
- Voice guides come from `article_tools.profile`. That store exists in Blog Studio only; if other studios get Apply a voice, the guides need to become shared.
- `google_plan` and `google_send`: the `google_suggestions` ledger, `google_workflow.snapshot_path` and `manuscript_editor.google_send`.
- `repurpose`: the `repurpose` tool kind and `desk.create`.
- The storage path `.blog-runs/desk-proposals`.

**Fit:** Humanize, Feedback, Headline and Proofread fit Training's documents as they are. For decks, a proposal's part becomes a slide id, and the brand audit should stay the source of slide findings.

### C.4 The job queue (`B/scripts/tool_jobs.py`): shareable as a core module with the worker passed in

Losing this costs a job: it stays stuck as "working" or it runs twice.

**Share:**
- `create`: idempotent by fingerprint, payload cap 1 MB, and a model snapshot through `studio_core.model_profiles`, which is already in core.
- `public`.
- `control`: cancel, and retry only for jobs that are not desk jobs.
- `recover`: on restart, an interrupted "working" job becomes failed.
- `once`, which:
  - picks the oldest queued job under the lock;
  - marks it working;
  - calls the worker outside the lock;
  - checks the result's shape and its 200,000-character cap;
  - runs the settle hook under the lock;
  - shares outside the lock, because the lock is not reentrant.
- `_working`, which drops a result whose job was cancelled or whose item was deleted meanwhile.
- `listing`.

**Blog-specific:**
- `KINDS` mixes the desk kinds with `voice-learn`, `voice-audition`, `voice-guide`, `style-learn`, `repurpose` and the interview kinds. Each studio should register its own kinds.
- The `DESK` tuple.
- The path `.blog-runs/tools`.
- `blog_runner.settings()['defaults']` for the engine and seconds.
- `model_profiles.route(saved, 'Blog Studio', 'draft', ...)`: the product name is hard-coded and every job is routed as `draft` (Part B.2 4). Core should take the purpose from the kind: quick for a selection, draft for a section, complex for a whole draft.
- The `team_workspace.guard` calls.
- The `desk-research` special case that calls `desk_jobs.research_run`.
- The `engine.worker`, `current`, `stop`, `wake` and `closed` events of `blog_runner.Engine`.

**Fit:** Blog's queue runs one job at a time for the whole studio. Training writes four levels, and Presentation already runs workers side by side (`SIDE_BY_SIDE`, `Slots`). The shared queue should keep one job per item but allow N slots for the studio.

### C.5 Page parts (`B/assets/management/desk.js`)

Ranked by what a person loses if the studios differ.

1. **Autosave and the stale banner: share.** `sDeskTyped`, `sDeskSave` and `sDeskFlush` save one second after the last keystroke against the revision the page last saw, with a session token. `sDeskStale`, `sDeskShare` (keepalive on leave) and `sDeskCounts` go with them. Blog-specific: only the route names (`desk-save`, `desk-share`).
2. **History, compare and restore: share as is.** These are pure functions: `diffWords`, `deskWords`, `deskCompare` and `deskAge`. `sDeskHistory` is a sheet. `DESK_SOURCES` holds the version labels; "Before an edit in chat" and "Before Google’s accepted text" are Blog's labels.
   - ui-kit already has a line diff (`.diff`, `.diff-row`, `.diff-sign`, used by Training's `comparison()`, `app.js:2144`).
   - Blog adds a second, word-level diff (`.desk-compare`, `.desk-plain del/ins`, `.diff-add`, `.diff-remove`).
   - Keep both in ui-kit, as a line variant and a word variant.
3. **Section cards with notes: share the card, pass in the words.**
   - Functions: `sDeskPart` (text, History (n), "How should this change?", Rewrite or Write again), `sDeskWhole` ("Note for the whole draft", "Revise the draft"), `sDeskWorkingIn`, `sDeskStatusWords` ("Revising section n of N…"), `sDeskJob`, `sDeskWatch`, `sDeskRefresh`.
   - Blog-specific: the Title and Opening parts, the `DESK_DOING` wording, and "Kind of post".
4. **Selection edits: share as is.**
   - `sDeskSelected` trims the selection and works out its offset in the saved part.
   - `sDeskSelectionBar` and `sDeskBarContent` give Rephrase, Shorten, Expand, Fix, and Ask… with Go and Cancel.
   - Nothing in them is Blog-specific.
5. **Progress screen: share.**
   - Functions: `sDeskProgress`, `sDeskEstimate`, `sDeskClock`, `sDeskSpent`, `sDeskElapsed`, `sDeskFollowStart`, `DESK_STEPS`.
   - The copy "Nothing needed from you. … in about N minutes", the beads and the one clock are generic.
   - It should gain the recovery that Part A.4 2 found missing; build that once, in the shared copy.
6. **Finishing panel: share alongside C.3.**
   - Shared: `sDeskPanel`, `sDeskToolList`, `sDeskToolView`, `sDeskProposals`, `sDeskProposal`, `deskSides`, `sDeskApply`, `sDeskSkip`, `sDeskComments`, `sDeskComment`, `sDeskToNote`, `sDeskProofView`, `sDeskFinding`, and the panel, drawer or sheet layout (`sDeskFloating`, `sDeskLayout`, `sDeskResized`).
   - Each studio supplies its own `DESK_TOOLS` list. Blog's Publish card, Repurpose, the Google card and `DESK_FORMATS` stay in Blog.
   - The `DESK_TOOLS[1][2]` bug (Part A.1 5) shows why the tool list should be keyed by name, not by index.
7. **Sources panel: share the panel, not the add sheet.**
   - Shared: `sDeskAside`, with Sources, Add a source, and "Needs you before publishing" (`.gap-items`).
   - Blog-specific: `sDeskSourcesSheet`, which wraps Blog's `sFilesCard` (roles, team library, Google Docs, keep in library). Presentation (`openBring`, `bringSheet`, `sourceFields`) and Training (`addDocuments`, `documentsCard`) have their own intake. Each studio passes its own add sheet.
8. **Start: share the frame, not the content.**
   - Shared: the three numbered steps (`DESK_START_STEPS`, `sWorkflowSteps`), the research ticks (`sDeskResearchDefault` on `research_sites`, already in core), the Start button and the problem line.
   - Blog-specific: `sDeskKinds` (kinds of post), `sDeskSettings` (`sFilesCard`, Length, Tone), `sDeskHave` (topic, outline or draft, the first pass, Google Doc intake), and the angles (`sDeskTopic`, `sDeskAskAngles`).
   - Presentation's `drawNew`, `stepsOf`, `documentStep`, `deckStep` and Training's `topicStep`, `shapeStep`, `startStep` already hold their own content. Note that the desk start is a full screen with steps; the Layout rules describe numbered steps for a sheet.
9. **Blog only:** `sDeskOutline` and its cards (sections with briefs; Training's blueprint or Presentation's outline could reuse it through the parts codec), `sDeskPublish` (Mark as published), `sRunOnDesk`, `sDeskRepurposeCard`, `sDeskGoogleCard` and `sDeskPrepublishCard`.

### C.6 Proofread (`B/scripts/text_checks.py`, `desk_finish.proofread`): share now, it is the easiest

- `text_checks.py` uses the standard library only and has no Blog imports: `mask_protected`, `lint`, `facts`, `preserve`, `carried_over`, `reader_facing_notes` and a command line. Move it to `core/studio_core/text_checks.py` unchanged.
- The `desk_finish` side can be shared over the parts codec: `_sentences`, `_sentence`, `_offsets`, `_mask_indented`, `_repetition`, `_openers` and `proofread`.
- Blog-specific: `proof_rules`/`_listed` read the BlogForge lists at `B/references/blogforge/voice/assets/ai-tells/{words,phrases}.txt`. Move those lists to core data.
- The rule labels are Blog's.
- The no-em-dash rule may disagree with a brand's own slide rules. For decks, the brand audit should win.
- Port the two run-only checks with it (`reader_facing_notes`, `carried_over`; Part A.3, Needs a decision 5).

### C.7 `blog.css` rules that belong in `ui-kit/style.css`

1. **Rules the Layout rules require of every studio that live only in `blog.css`:**
   - Filters: `.filter-bar`, `.filter-bar .search`, `.more-filters`, `.filters-toggle` and the phone rule that shows only search (`:23-30`, `:136-139`).
   - Selection bar: `.library-selection`, `.selection-count`, `.selection-actions`, `.panel-heading .select-page` and the phone placement (`:118-135`). Rename it `.selection-bar`.
   - Numbered steps in a sheet: `.create-flow`, `.create-step`, `.create-foot` (`:148-153`). They overlap ui-kit's `.sheet-part`.
   - The sticky sheet header: `.sheet-heading` (`:91-93`).
   - Page spacing: `#studio-page>*+*{margin-top:1.1rem}` (`:16`).
2. **The desk layout, generic once named for the shared module:**
   - `.desk-layout`, `.desk-column`, `.desk-aside` (two columns at 1100px, sticky aside), `.desk-finishing`, `.desk-finish`, `-head`, `-title`, `-body`, `-sheet` (panel, drawer, full sheet).
   - `.desk-part-head`, `.desk-text`, `.desk-note`, `.desk-note-text`, `.desk-working`, `.desk-working-note`, `.desk-problem`, `.desk-stale`, `.desk-save-state`.
   - `.desk-selection`, the fixed glass bar above the tab bar.
   - `.desk-versions`, `.desk-version`, `.desk-compare-area`, `.desk-compare`, `.desk-plain`, `del`/`ins`, `.diff-add`, `.diff-remove`.
   - `.desk-proposal`, `.desk-sides`, `.desk-side`, `.desk-quote`, `mark`, `.desk-edit`, `.desk-comments`, `.desk-comment`.
   - `.desk-steps`, `.desk-clock`, `.desk-outline-part`, `.desk-angles`, `.desk-angle`, `.desk-angle-picked`, `.gap-items`.
   - All of `:168-225` and `:98-103`.
3. **Shared research choice:** `.research-choices` and `.site-choices` (`:110-116`). Presentation (`researchFromField`) and Training (`researchFields`) draw the same control.
4. **Two-column gate:** the `.gate` media rule (`:50`). ui-kit's `.gate` is single-column, and `.desk-layout` repeats the same shape.
5. **Duplicates to fold into what ui-kit already has, not move:**
   - `.decision-notice` is the same as `.callout[data-kind="yours"]`.
   - `.context-note`, `.dialog-notice` and `.sync-status` are the same as `.callout` or `.notice`.
   - `.help` and `.footnote` are the same as `.quiet` or `.field-hint`.
   - `.error,.problem{color:var(--late)}` (`:42`) and `.sheet .input{max-width:none}` (`:13`) restyle shared classes from a page stylesheet, which `golden-gate.md` forbids.
6. **Stay in `blog.css`:**
   - The library table (`#editorial-screen`, `#results`, `.view-library`).
   - `.import-post-list`, `.author-*` and `.sample-picks`.
   - The old editor's `.manuscript-input` and `.polish-intake`, and its review styles `.writing-change`, `.change-*` and `.review-*`. These belong to the old flow.
   - `.source-choices`.
   - The dead classes listed in Part A.3 Safe 7.
