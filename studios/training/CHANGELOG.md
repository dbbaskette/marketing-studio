# Changelog

Unreleased: a deck no longer stops at "Presentation ID must be a Google Drive ID". A render that failed in the slides tool's shared preview files left a receipt, not a Drive file, as the deck's remembered preview; the deck's own named file is now made new when that is all there is.

Unreleased: a deck drawn from an approved design no longer stops at "The preview deck changed while it was being read". The render the review is made from is now taken again, up to three times, and kept in a Drive file of that deck's own, named after it, as the ordinary whole-deck preview already was. The earlier fix had missed this path.

Unreleased: what a deck says comes to you as text before any slide is drawn, again. **Approve the slide text before the deck is drawn** is ticked to start with on the form; untick it to have the deck drawn straight from its words. Trainings already started keep what they began with.

Unreleased: a deck's Google preview is steadier and easier to find. A preview Google changed while it was read back is taken again, up to three times, before the training stops for it. The whole deck's preview is kept in a Drive file of that deck's own, named after it, not in one of the slides tool's shared "Harness Slides preview" files; a section's working previews still use those.

Unreleased: a stop reads cleanly. The **Your move** card says what went wrong in one line and wraps long words; the full account stays in the stop under it, without the slides tool's command-line advice or a raw address.

Unreleased: a new training no longer stops when the independent check flags research. An assistant decides each flagged item: it keeps minor points, warns where the doubt is real, and leaves out only a very important claim that a source directly contradicts, with newer documents usually winning. Each choice and its reason is kept in the evidence as automatic, never as your decision. Tick **Decide flagged research myself** on the form to keep the choices; trainings already started keep them.

Unreleased: assistant work is never stopped for how long it takes, because ending it discards what it had done. **The longest a step may take** is gone from Settings, a time saved there is kept in the file and ignored, and a step runs until it finishes or you press **Stop**. Only the Quick scan keeps its 4.5 minutes, since it has an outline to fall back on. A training saved while stopped for time carries on with **Give it more time and try again**, now with no limit.

Unreleased: a deck is drawn straight from its words. The stop to approve slide text is now asked for: tick **Approve the slide text before the deck is drawn** on the form. Trainings already started keep the approval they began with.

Unreleased: Fable 5.2 is in the Claude Code model list, and **Fable, always the newest** now means it.

Unreleased: the assistant has 50% more time before a step is stopped. A step may take up to 22.5 minutes, not 15, the Quick scan 4.5 minutes, not 3, and the final brief of sectioned research 7.5 minutes, not 5. A limit you already saved in Settings, under Limits, keeps its value.

Unreleased: spending limits are removed. The project spending amount in Settings, the **Spending behavior** choice and the spending warning are gone, and work no longer stops or warns for what it costs. Time limits, tries and an account's own usage limit still apply, and the desk still shows what the assistant reported. Saved work that stopped at a spending limit carries on with **Carry on**.

Unreleased: the desk's status lines agree. A training that is still being written says its finished drafts are ready to read, on Home and on the desk, and asks for them only once it waits on you; the arc stays on Make while drafts are read and reaches Ship when every material is ready. The rail is as tall as its own parts, and the workflow, **About Ready and delivery** and the activity log sit under the material.

Unreleased: a training's desk is a workbench. Its materials are listed on the left, the material you are reading fills the middle, and one rail on the right holds the Brief, Plan, Make, Ship arc, **Your move**, and what the assistant is doing. Press **F** to read the material alone.

Unreleased: a training's stages are one drawn line, the progress track, with the stage waiting for you in amber; **Search and jump** (Cmd or Ctrl+K) and a Light, Dark or Auto appearance sit at the foot of the sidebar.

Unreleased: the desk says where a level stands in one line (ready to read, marked ready, awaiting your review) with **What is left** under it, and the progress line offers finished drafts instead of saying nothing is needed while they wait. A deck now needs Harness Slides 0.17.0 or newer.

## Unreleased — 4.14.0

Each finished draft can be marked ready as soon as it is written, while the materials built from it are still being made. Marking a whole level at once still waits until every material in the level has a draft.

Completed research sections expose saved read-only prose before final checking. Previews name their revision and assigned sources and remain ineligible for delivery. Queued concerns save privately across reloads without changing evidence or starting work; apply actual changes through the existing explicit refresh/impact flow. Timing separates the first readable section from the checked result.

## Unreleased — 4.13.1

Idle desks check a compact change signal before reading content again. Active work keeps its existing cadence; focus and reconnect catch up immediately. Incomplete metadata checks fall back to full reads, and connection failures back off.

## Unreleased — 4.13.0

Slide-text review shows one slide at a time with a compact picker and collapsed speaker notes. Corrections, feedback and selection save privately across reloads without starting work. Earlier corrections remain available when the outline changes; approval uses only the exact validated current text.

## Unreleased — 4.12.0

New work warns and continues at its project spending amount by default. Shared settings can choose Stop and ask; saved work has an explicit, stale-safe spending choice. Old tasks keep hard-stop behavior and Carry on. Warning mode supplies a $5 budget per job, keeps smaller Quick-scan budgets and time limits, records crossings once in Activity and shows them on the desk and home. Dollar enforcement and reporting depend on the assistant. Policy saves start no work or new research.

## Unreleased — 4.11.1

Saved work publishes compact metadata for Marketing Studio’s Needs you, In progress and Recent work overview. Direct resume opens the saved editing/decision context. Metadata browsing starts no studio or provider work.

## Unreleased — 4.11.0

New section workflows preview affected research before refresh. Added sources can target selected sections; changed or removed inputs require wider invalidation. Retained investigator packets and drafts are revalidated, and assembled research still needs a fresh independent check. Wording, notes-only edits and existing section updates keep their direct routes.

## Unreleased — 4.10.0

New outline-first work keeps section contributions across retries, combines at most three at once, and gives only a timed-out contribution more time. A short final author reads the contributions; the supported independent whole-report check still gates use. Existing saved flows retain their schemas and helper versions.

## Unreleased — 4.9.1

- Share strict provisional-outline validation and bounded source excerpts with Presentation
  Studio; the saved Training Studio workflow and approval contract remain unchanged.

## Unreleased — 4.9.0

- Outline-first records use schema 7 so older runtimes refuse to drive them. Existing
  schema-6 topics-review records keep their saved flow.
- New runner trainings start with one bounded Quick-profile scan and an editable outline.
  Save edits without assistant work; only Approve outline & research starts detailed
  research. Removing a section removes its research scope. Form questions stay visible.
- The scan uses bounded excerpts, no external searches, at most 180 seconds and $0.25
  within existing training limits. A stop or time cap keeps a usable incomplete outline;
  no automatic second author or escalation runs.
- Approved sections use the pinned Harness Research collection protocol, at most three
  areas at a time, followed by the existing combining and whole-dossier independent
  check. Materials receive the approved scope and checked evidence. Supplied-only stays
  supplied-only; the provisional scan is never research evidence.
- Existing work keeps its saved flow. Eligible stopped work before a report/teaching plan
  can explicitly adopt after a preview; inputs, spending and private unfinished research
  history are preserved. Adoption starts no job and waits for Resume training.
- Presentation Studio's corresponding outline-first flow remains a separate cohort.
  Independent section-review receipts and later incremental research reuse remain later
  companion work; no Harness Research protocol was changed here.
