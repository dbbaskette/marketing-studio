# How it works

This page explains what Training Studio does behind the conversation. [The runner](runner.md) describes a training made on the page as it is now. The first [design](superpowers/specs/2026-10-12-training-studio-core-pipeline-design.md) is kept as history.

## The desk

New trainings run without review stops. The desk shows materials as they arrive; you can edit them or request changes while work continues. When an input changes, dependent materials may be held until you explicitly update them or keep them as they are. Mark ready is your approval, and the index is written once the requested materials are ready. See [the desk](the-desk.md). Trainings started before the desk retain their saved review flow.

## The stages

| Stage | Done by | Produces | Gate |
| --- | --- | --- | --- |
| Intake | Training Studio | `intake.md` and your settings | |
| Research plan | Training Studio | Up to 8 synthesis questions; 30 in legacy queues | 1 |
| Research | The harness-research skill | A cited report | 2 |
| Blueprint | Training Studio | Objectives, modules, assessment and practice plans | 3 |
| Document | Training Studio | The learner guide | 4 |
| Brief | Training Studio | A product or competitive brief | 5 |
| Deck | The harness-slides skill | Google Slides or PowerPoint | 6 |
| Scenario | You and Training Studio | Scenario files | 7 |
| Yoodli, optional | Training Studio | A Yoodli scenario for each scenario file | 8 |
| Package | Training Studio | The index and a readiness report | |

In a conversation or a saved run, at each gate you approve, ask for changes, have it rebuilt, or skip. With levels, intake and research happen once, all the blueprints are reviewed together, and gates 4 to 8 then repeat for one level at a time.

The blueprint is the hub. The document and brief are written from it, and the deck is built from the blueprint and the document. A Yoodli scenario is built from your scenario file, the brief and the blueprint.

A new training on a Harness Research without synthesis is refused at Start. The legacy question queue is kept for a training begun before the synthesis research contract, so that it finishes as it began. `studio saved-work` lists any that still need it.

## Where facts come from

The research is written by one agent and checked by another, which reads every source the report quotes and, for a document you supplied as a PDF, a Word file or a web page, the file itself. When the check could not read what it must vouch for and the studio cannot serve it either, the research stops at once and says so, rather than spending rounds of correction on it.

Every claim in the blueprint and the brief names the research finding it rests on. A finding is supported, contradicted, insufficient or unavailable; the last two are called unresolved. Only a supported finding can back a claim. A contradicted one can back the correction of a misconception, or the answer to an objection. Where the research could not establish something, the training says so under open gaps and the brief lists it under Unknowns. Nothing is filled in from the assistant's memory.

## Approval and changed inputs

Each file has a status:

| Status | Meaning |
| --- | --- |
| not-started | The file does not exist yet |
| draft | Not approved in its current form |
| approved | You approved exactly this content, built from exactly these inputs |
| out of date | Something it was built from has changed since |
| skipped | You chose to leave its stage out |
| unavailable | Its stage could not run |

Status is worked out from the files each time, so editing a file by hand is safe and is always noticed.

An approval covers both the content and what it was built from. Three consequences:

- Edit an approved file and it becomes a draft. Anything built from it becomes out of date.
- Rebuild a file against changed inputs and it needs approving again, even if the text came out the same.
- Accept an out-of-date file as it is, with a reason, and only that file is approved. Files below it stay approved only if their own inputs did not change.

Changing a setting affects only what uses it. A new brand makes the deck out of date and leaves the research alone.

## Where you approve

Every decision at a gate is recorded with where it was made, and written into that file's review under `reviews/`.

- **In the conversation.** You tell your assistant, and it records your decision. This is the default.
- **On the page.** You decide on [the page](page.md) in your browser. The helper then refuses `approve` and `skip` from the command line, so your assistant cannot record a decision you did not make. Asking for changes or a rebuild leaves a request your assistant acts on when you return to it; the request closes when the file is rebuilt or approved, and an open request keeps the training from being ready.

Moving a training to the page raises the bar; it does not make forgery impossible. An assistant with a shell that set out to rewrite the session record could still do so. The guidance forbids it, but only [the runner](runner.md) prevents it: there, each agent works in an empty folder outside your trainings, with no shell, and has no way to approve.

## Ready, or not

`check` reports two things. **Checks passed** means nothing it could check has failed. **Ready** means the training is complete: every wanted file is approved, nothing is out of date, no check failed or could not run, and no Google Doc or Word copy you asked for is out of date. A question still waiting on you also blocks it. It lists what is blocking, and separately what was left out because you skipped it, it could not be produced, or you accepted it as it was after something it was built from changed.

Some checks are stronger than others, and the report says which:

- **Document coverage is declared.** Each section says which objectives it teaches. That proves the claim was made, not that the prose teaches well.
- **Deck coverage is reviewed.** The assistant reads the finished slides and records what it found. The review is tied to that exact deck and stops counting if the deck changes.
- **Practice is reported.** The report lists which objectives your scenarios exercise. A scenario need not cover them all.

## The training folder

```
valkey-training/
  README.md                index and readiness report
  intake.md
  research-report.md       the approved research report
  blueprint.md
  document.md              and document.docx, if you asked for Word copies
  product-brief.md         or competitive-brief.md; its .docx with Word copies, or for Yoodli
                           when you keep no Google Docs
  deck-handoff.md          the note given to harness-slides
  deck.pptx                or deck-link.md for Google Slides
  scenario.md              your scenario; more go under scenarios/
  yoodli/main.md           optional: the Yoodli scenario built from scenario.md
  reviews/                 what you were shown at each gate, and what you decided
  work/                    the assistant's working files; nothing here is a deliverable
  sources/                 the documents you selected
  .training-studio/        the session record and every earlier version
  .harness-research/       owned by harness-research
  .harness-slides/         owned by harness-slides
```

With levels, `intake.md`, `research-report.md` and `sources/` stay at the top, and everything from `blueprint.md` down sits in a folder per level: `101/`, `301/`. Each level's deck is built as its own harness-slides task inside that folder.

Every version of every file that was saved or approved is kept under `.training-studio/history/`, so an earlier version can be restored.

## Guidance and scripts

What your assistant follows is guidance: instructions, templates and the Yoodli field data. What changes files is a small set of scripts.

- Scripts are installed and never fetched.
- Guidance is fetched from this repository's `main` branch when a new training starts, and that training is pinned to it. The pin records the exact commit.
- Guidance is only ever what the helper fetched from `main` itself. It is kept in the per-user data folder, by commit, and checked against that commit's own files each time it is used. Of a training's pin, only the commit is read: a training copied or brought from elsewhere cannot bring guidance with it. A pin naming a commit that is not on `main` is refused, and nothing is fetched by commit.
- git runs apart from your own setup: no system or global config, no `GIT_*` variables, no hooks, no replaced history, and only `https` or a local folder to fetch from. The helper's copy of `main` is used only as it made it; anything else is deleted and fetched again.
- A pinned training needs no network to resume.
- If guidance cannot be fetched, the guidance installed with the scripts is used, and you are told it may be older.

See the [phase 2 design](superpowers/specs/2026-10-12-phase-2-packaging.md).

## The helper

The skill drives a small command-line helper, `skills/training-studio/scripts/training.py`. The installer writes a command that runs it with a Python new enough, whatever `python3` is: `~/.local/share/training-studio/training`. Your assistant runs the helper through it. You never need to run it, but you can, as in `~/.local/share/training-studio/training status`:

| Command | Does |
| --- | --- |
| `status` | The stage, what is waiting, and the status of every file |
| `check` | Runs every check that applies and reports readiness |
| `save`, `approve` | Record a version, and record your approval of it, which moves the training on once its stage is finished |
| `export` | Makes a Word copy with pandoc and records it, when you asked for them. Without pandoc, it records why there is none |
| `google` | Sends the guide or the brief to a Google Doc and brings edits back |
| `skip` | Leaves a stage out, or brings it back |
| `checkpoint` | Records where the run stopped and what is at the gate, and changes settings such as which copies to keep. `--add-level` adds a level; a level with work in it is never dropped |
| `list` | The trainings on this computer |
| `desk` | Serves [the page](page.md) until it is stopped |

`--help` after any command lists its flags and the values each takes. A reason is always given with `--reason`, and a list is separated by spaces. A refusal says what puts it right.

It needs only Python and never commits to git. Apart from `google`, the team hub and, on the page, the check of this computer that you ask for, none of it touches the network. The assistant's instructions for using it are in [the workspace reference](../skills/training-studio/references/workspace.md).

## Research from your documents

For supplied-only synthesis, Training Studio writes the plan from the optional questions
on your form and runs no planning assistant. Research itself remains with Harness Research.
The research stop shows its brief, independent assessment, gaps, source limitations and
question mapping. Research changes rerun the whole investigation and downstream made
materials; the request says the scope and last recorded cost before it is sent.

## Research from your sites

A training may research from your documents, your sites and/or the public web. Your sites
are base addresses; the form starts from the list every studio shares and may add one for
that training only. The run pins the exact list. Its research task names the allowed sites,
and its worker tools save a page only from under them, checking every redirect, unless the
public web is chosen too. Pages from your sites are public captures, so documents and sites
together are Harness Research's `mixed` source mode and sites alone `public`. See
[Where the research looks](runner.md#where-the-research-looks).

## Finish from the page

New combined-review runs prepare every level's guide and deck direction first. Balanced waits for the first review; Automatic draft continues under its saved policy. Briefs are written afterwards. Existing runs keep their saved review order. The first and final combined reviews have timeline beads, and the last decision stays visible while work continues.

Download buttons take away supported made files, Word copies and the finished index. Google changes are looked for, and pulled, only on request: **Look for changes in Google Docs** asks Google, and **Bring the Doc's changes in** brings a change in. When both texts changed, both are kept and a confirmation chooses which text replaces the other; later edits require another pull. Yoodli fields can be copied from the final review and Done.
