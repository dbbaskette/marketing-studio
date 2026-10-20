# Workflow review: making the studios smooth, with control where it matters

Reviewed 2026-10-20 on merged `main` (`193b151`). Three read-only walks of every page a person passes through in Blog Studio, Presentation Studio and Training Studio, from "I have an idea" to "I'm done", on desktop and phone. Line references are to each studio's `desk/app.js` or `assets/management/runner.js` unless stated.

Effort: S ≈ under a day, M ≈ a few days, L ≈ a week or more.

---

## 1. The same five problems, in every studio

The three reviews found the same shape of problem three times. Fixing these as one shared pattern is cheaper and makes the studios feel like one product.

| # | Problem | Blog | Presentation | Training |
|---|---|---|---|---|
| A | **The start form promises stops the review level removes.** The level is set only in shared setup; the form doesn't show it, and lists every gate as if Step by step. | Wizard always says "outline, then draft" (runner.js:143); two New-blog entry points with different hidden defaults (:52/:131 vs :232) | `asksFor()` lists every gate regardless of level (:2814) | "review the teaching plan, then the finished materials" (:4161) hides that every level's guide and brief are written first |
| B | **A black box while working.** No elapsed time, no "what it's doing now", cost only in a collapsed card, no way to add a note without stopping. | No start time recorded at all (blog_runner.py ~1012) | Section being drawn only visible as a worker's last line (:4180) | One sentence, flat step list across levels (:4396, :4485) |
| C | **Try again / Stop don't say what they cost.** | "Try again" reuses the same time limit that just expired (:153) | Doesn't say that 2 of 4 sections are kept (:3160) | Re-runs the whole research job (~5 min, ~1M tokens) silently; Stop says "everything kept" but discards the step in hand (:121, engine.py:2591) |
| D | **The sticky toolbar overflows on a phone.** 4–6 capsules wrap into 2–3 rows and eat ~40% of the screen. | :153, :164 | :4639 | :4957 |
| E | **Developer words and inconsistent verbs.** | 4 names for the editor; 3 titles for the board (:308, :153, :109) | "First native build", "AI critique", "Render 1a2b3c" (:2843, :3965, :3902) | teaching plan / blueprint / direction; "In the way" |

**Shared fixes (do once in `ui-kit` + each controller):**
1. **A "stops for you" line on every start form**, computed from the shared review level × that studio's pipeline, with a "Change" link. Make Approve one tap everywhere; keep confirm sheets only for Stop and anything that costs money. (S each)
2. **A "now" line under every run's title**: step · part (section 2 of 4 / level 201 guide) · elapsed · spent so far · stop limit. Record `started_at` in every runner. (S each)
3. **A "Note for the next step" box on every run screen** that writes into the next job's request without stopping the worker. Blog's `request`, Presentation's `extra`, Training's `answers` all already carry free text. (M total)
4. **Honest retry and stop copy**: "Try again re-runs research from the start: about 5 min and ~1M tokens" / "Try the slide build again: 2 of 4 parts are kept" / "Stop loses the step in hand; Pause lets it finish". (S each)
5. **One primary action on phones**; the rest go into the existing `.menu`. Sheets bottom-anchored below 52rem. (S–M each)
6. **A wording pass**: one noun per thing per studio (draft / deck / training; outline / blueprint; direction review / final review), and no "native", "AI", "render", "run details" in person-facing copy. (S)

---

## 2. Blog Studio

**Today:** idea → readable draft is 6 taps, 3 fields, 2 waits; but via the toolbar the draft is never a stop. Draft → "published" has no step at all; recording it takes 7 taps through the legacy board.

1. **One entry point, truthful stops.** Toolbar "New blog" opens the same start cards as Home. Drop "Normally stop after" from Blog Studio Settings; the review level governs stops. (S) *(pattern A)*
2. **A real finish.** At the final stop, show the draft open (not collapsed under the package) with "Finish". Then a "Done" card: Copy Markdown · Download · Mark as published (URL) · Delete. Today the only offer is "Polish". (M)
3. **Ideas gate becomes a pick.** "Develop an idea" asks for free text though the model returns three angles. Parse the outline headings into pick cards with an optional note. This is the same control the upload flow uses (section 5). (M)
4. **Elapsed time and retry with more time.** Record `started_at`; show "Drafting · 3 min of up to 10"; offer "Try again with more time" after a time-limit failure. (S) *(patterns B, C)*
5. **Keep diagnostics.** Unexpected worker errors become "The worker failed"; stderr is discarded. Keep a tail under `.blog-runs/diagnostics` and show "What went wrong", as the editor already does. (M)
6. **Remove ceremony:** the "I checked this preview" checkbox on Google import; per-blog Assistant and Time-limit fields in the wizard (defaults masquerading as decisions); "Interview me" re-asking title/audience/goal it already has. (S)
7. **Lists by recency**, not alphabetical id, so "Needs you" surfaces what just changed. (S)
8. **Legacy header**: hide the Hub access panel unless a Hub is selected; merge "Editorial pipeline / Blogs in progress / Writing pipeline" into one title. (S)
9. **Phone:** Copy Markdown beside blob downloads; hide folder import on touch. (S)

**First three:** #1, #4+#5, #2.

## 3. Presentation Studio

**Today:** topic → deck is 6 taps and 2 waits, which is fine. The problem is what the taps don't let you do.

1. **"Change what it says."** At the build gate and on a delivered deck the only offer is "Ask for changes to this slide", which redraws; the composer is forbidden to change words, and findings tagged "About what it says" can't be acted on. Add a second decision that reopens the outline with the named slides pre-marked, then rebuilds only their sections. The single most common revision ("slide 4 is wrong") currently dead-ends. (M)
2. **Honest "Ask for changes" on a finished deck.** The sheet has no slide picker there, so every section is redrawn; the copy says otherwise. Keep the per-slide chip on the Delivered screen and warn "No slides marked: the whole deck is drawn again (~$X, ~N min)". (S)
3. **Let the person correct the spec/material classification.** Balanced auto-accepts it and the direction review doesn't show it; a wrong verdict makes the whole outline wrong. One line in the direction review with "That's wrong". (M)
4. **Collapse the start step.** Five cards, one real decision (brand, prefilled). One "Options" fold with a summary line; remove the regex that silently flips "first draft" from goal text. (S) *(pattern A)*
5. **Storyboard redraws itself** 1.5 s after the last edit, old frame greyed until the new arrives. (S)
6. **Carry mid-build slide feedback forward** instead of refusing it when the section finishes; pre-fill it as that slide's mark at the build gate. (S)
7. **Per-slide notes at the build gate**, as the outline gate already has. (M)
8. **One Approve**: toolbar keeps the decision, review bar shows only the tally. (S)
9. **Fix the finding tags**: page expects `content|concept`, runner emits `drawing|content`, so one tag never shows. (S)
10. **Explain Undo**: "Undo: Draft the outline (3 min, $0.60)". (S)
11. **Phone:** timeline beads lose their names below 52rem (no caption is emitted); outline rows carry four buttons each. (S)

**First three:** #1, #2, #4 with the shared "now" line.

## 4. Training Studio

**Today:** the owner's Status-page confusion is real: one training listed twice, legacy "0 of 1 questions" wording, "Last changed 1 hour ago" while running, "In the way: 6 things" unexplained.

1. **One Status table**: Training · Doing now · Cost · Last activity · Open. Research wording for schema-3 runs: "Investigating sources and writing the report (job 1 of 2)" / "Independently checking the research". "Last activity" = max(touched, newest job end, worker start). "Still to make: 6" for in-progress trainings; "In the way" only for finished-but-not-ready. (S, all four)
2. **Make the research plan a real stop under Balanced.** It's a 30-line read and the cheapest, highest-leverage decision; today it auto-continues and the person first sees the questions after ~5 min of research plus blueprint, guide and brief for every level. Alternative: auto-continue but show the plan with "Change the questions" for a window. (S)
3. **Say when the direction review arrives**: "after research, blueprint, guide and brief for each level (about N min)". (S) *(pattern A)*
4. **Defaults shouldn't build the maximal training.** All three materials and a PowerPoint deck are preselected; levels hide in a disclosure though each multiplies cost; the deck needs a brand skill the default can't guarantee. Start materials empty, deck "No deck" unless a brand is set, levels as chips in the open. (S)
5. **Per-training review level** on step 3 (default = shared). (M)
6. **One place to ask for changes**: under Balanced the per-file gate is read-only with a link to the direction review; today two ledgers can restart a step mid-review. (M)
7. **Batch change requests**: collect per item, one "Send N requests" with a preview of what gets rewritten (a research change invalidates every level's blueprint/guide/brief, silently today). (M)
8. **Honest Try again / Stop**, and a failed sample slide becomes a note, not a halt. (S) *(pattern C)*
9. **Per-level progress strip** with elapsed and spent, plus the shared note box. (M) *(pattern B)*
10. **Soft controls**: "Finish this level, then wait", "Skip the deck for now" (sheet exists). (M)
11. **Phone:** the combined review is a wall with Approve at the top; per-item chips and a sticky bottom bar. Copy buttons per Yoodli field. (M, S)

**First three:** #1, #2+#3, #8.

---

## 5. The two features you asked for

Both fit the patterns above and reuse what exists.

### Build a blog from uploaded content

Decided: your files first, web research as an off-by-default switch; three suggested angles, you pick one; then outline → draft under the normal review level.

**Today** it takes ~7 taps across two screens, one file per upload, and a PDF silently contributes nothing (the page can't extract PDF text; it's saved "pending").

**Flow (one screen, then the normal run):**
1. Home → **"Write from my files"** card (alongside Write from a brief / Use my outline / Explore ideas).
2. One screen: a multi-file picker (md, txt, html, docx, pdf; up to 10 MiB each), an optional one-line "What's this for?", and the switch "Also research the web to fill gaps" (off). Files upload in one request; each shows extracted size or "needs text" so nothing is silently empty.
3. Start → a short **angles** job reads the files and returns three angles (title · audience · the point it makes · which files it leans on). The gate shows them as pick cards with an optional note; "None of these" asks again with the note. This reuses the Ideas-gate pick-card fix (Blog #3).
4. Picking an angle creates the normal run with those files pinned as sources, research = supplied-only (or web-allowed if the switch is on), stop per the review level. From here it's the existing outline → draft → finish path.

**Under the hood:** `/api/upload` gains `multiple` and a `purpose: material` that doesn't add files to the permanent reference library unless asked; PDF text extraction via the bundled `pdftotext` the slide studios already use; the 300 KB context cap becomes excerpting (the existing `passages` helper, page-side) instead of a refusal; a new `angles` step in `blog_runner` and a `from-files` mode.

### Delete blog (with 30-day restore)

Decided: delete stops any running job, removes the blog from lists, keeps it in Git history, and a "Recently deleted" list restores it for 30 days.

**Flow:** Delete lives on the run's "Done" card and in More tools. Confirm sheet names the blog, says what's running will stop, and asks you to type the title (as Training Studio's delete does). After deleting, Blogs shows a "Recently deleted (1)" fold with Restore.

**Under the hood:** copy Training Studio's delete (`runner/engine.py:3750`, `page.py:51-56`, `tests/test_runner_delete.py`). A top-level `blog-delete` route (not `run-*`, whose post-action would recreate the folder); stop the engine job and wait for `current != id`; remove `.blog-runs/<id>.json`, `.active-article.json`, desk receipts and upload caches that name the id; in a team workspace use `gitstate.remove` + push so the next refresh doesn't refuse; in Hub mode tombstone the item. Restore = `git revert` of the deletion commit plus re-creating the ignored state; a `deleted_at` list under `.blog-runs/deleted/` drives the 30-day fold.

---

## 6. Suggested order

1. **Training Status page** (section 4 #1): a day, fixes the confusion you hit.
2. **Shared "stops for you" + "now" line + honest retry/stop** (section 1 #1, #2, #4) across all three studios.
3. **Delete blog** and the Blog **finish** card together (they share the "Done" surface).
4. **Write from my files**, which builds on the Ideas pick-card gate.
5. **Presentation "Change what it says"** and the Delivered-screen slide picker.
6. Phone toolbar/menu and sheets, then the wording pass.
