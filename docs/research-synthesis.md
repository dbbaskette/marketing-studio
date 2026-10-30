# Shared synthesis research

New browser runs use Harness Research's synthesis contract when the installed
helper supports it. Blog Studio, Presentation Studio and Training Studio share
`studio_core.research_contract`; they keep their own source permissions, worker
confinement, model profiles, stop controls and review levels.

The companion lock selects the stable **1.1.0** release at an exact commit and
checksum. Harness Research accepts newer stable releases through `>=1.0.0`;
Harness Slides also retains stable `>=` selection. Prerelease tags are excluded,
and each resolved release is locked to its commit and source checksum.
Installing/updating companions remains an explicit action. Merely opening a
studio never downloads or replaces tools. New runs on an older installed helper
retain the older adapter; existing runs never change research formats on resume.

## Handoff and execution

The studio passes its actual task as ordinary-language `purpose`, separately from
`audience`, `scope` and `source_mode`. Presentation research prioritizes messages
and visual explanation, blog research the argument and objections, and training
research the concept sequence, misconceptions and grounded examples. Planning
questions are investigation aids, not a required report outline or answer quota.

The confined author invocation reads the helper's investigation and synthesis
guidance, its own stage references; the studio-handoff guidance is the studio's to read.
It is told that the studio's tools saved every capture, and to cite each by the path they
gave. Its dossier includes an authored brief, typed findings,
supporting facts, counterfacts, conditions and gaps. The parent validates captured
source identities and permissions, then asks the helper to save it. Another
invocation independently checks the exact digest's evidence, findings, report and
brief. Both use the saved Main model profile. Neither can approve a studio gate
or publish content. A rejected review allows two bounded correction cycles;
unresolved work stays a saved draft and blocks downstream authoring.

The check attests that it read every source, and the original of each supplied
source that has one. Its tools serve both: `read_source(source_id, original=true)`
and `search_source(..., original=true)` read the original, text as it is and a PDF
or Word file as the text read from that file at the time, after a line with its size and
SHA-256; `list_inputs` names each original beside its source. An original is only
claimed when it is another document than its capture: a PDF, a Word file or a web
page. A text or Markdown document, such as a Google Doc's Markdown export, is its
own capture, so the check is asked for nothing more. The studio decides which
sources have an original; one a previous draft named and the studio no longer
offers is dropped.

When a review's only objections rest on sources whose original the check says it
could not read (every unsupported verdict rests only on such sources, and the
assessment asks for no revision), no correction by the author can change its answer.
Only a source with an `original_file` counts: one whose capture is the document is the
check's to read. The contract then asks the studio, through `Workflow.run`'s
`readable` callback (`dry_read` for the studios), whether its own tools can serve
that original. When they can, the check failed, not the studio: the next round goes
ahead, and if the rounds run out the usual grouped refusal applies. When they cannot,
the contract stops before the next author round with `CheckCouldNotFinish` (a
`ReviewRefused` with a `cause` naming each source and the studio's answer), and that
round is not counted. The studios stop at the research step saying it is a studio
problem, not a research problem, and refuse Try again in the same words while the dry
read still fails. A refusal after the last round counts
its objections by cause ("12 facts the check calls narrow (…), 3 findings
unsupported (…), coverage needs revision (…)"), lists each one under its group in
the studio's research review, and says what the try's research jobs took in time
and money. `ReviewRefused(objections, rounds)`, `objections(case)` and the
`objections` and `rounds` of the error `native` raises are unchanged; `groups`,
`cause` and `spent` are added beside them.

Blog Studio first discovers at most eight public URLs when public research was
allowed. The parent fetches actual bounded source bytes through the existing
public-address-pinned HTTPS reader. Search snippets and generated source text
are never registered as evidence. Supplied-only runs never search or fetch.
Presentation Studio and Training Studio retain their existing confined source
capture tools, including selected original document pins.

## Live research progress

All four studios use `StudioResearch.progress` from the shared UI kit. Its compact
robot counter counts invocations observed by the host, including investigation,
synthesis and independent review. Harness Research owns collection evidence and
workstream identity; the host observes invocation starts and terminal outcomes.
Configured worker capacity and completed packets are not live agent counts. The
counter expands with native keyboard-accessible details to show each active role.
It introduces no library or provider request.

The heading names the current stage and its position out of three. Each stage
has a visible complete, working-now or still-to-do label; the active stage has
an accent fill as well as `aria-current`. The activity sentence says what is
happening, followed by what remains. Collected evidence collapses during synthesis
and review, so completed source cards do not imply the whole research is done.

The progress callback adds `agents: {count, unconfirmed, active}`. Active entries
carry an ID, phase, optional workstream and observed status. Start/end callbacks
publish new snapshots without waiting for an entire research area to finish.
An unconfirmed termination makes `count` null; legacy snapshots without this field
show an unavailable count. Neither case claims zero workers. Host execution
records stay in the existing private, ignored case directory.

| Transition | Screen behavior | Regression coverage |
| --- | --- | --- |
| Investigation starts/ends | Live robot count follows observed invocations; current stage has accent fill and `aria-current` | `SessionTests.test_live_agents_follow_actual_invocations_in_every_phase`, shared component and browser checks |
| Evidence collected → synthesis → independent review | Kept evidence remains visible; each active writer/reviewer counts as one | Shared session tests and Training Studio browser journey |
| Review requests evidence corrections | Next correction round identifies affected areas and exposes reviewer reasons; unaffected packets remain kept | `SessionTests.test_fact_correction_recollects_only_affected_area` and browser correction state |
| Review requests prose corrections only | Recombine and recheck; never show a new investigation | `SessionTests.test_prose_correction_does_not_recollect_evidence` |
| Terminal observation unavailable | Show an unknown count and confirmation wording; keep capacity occupied | `SessionTests.test_unconfirmed_terminal_invocation_blocks_generation_restart` |
| Stop requested → termination confirmed | Retain the final activity callback for the same run; show stopping until the count reaches zero, without adopting incomplete research | `ParallelNativeTests.test_stop_keeps_terminal_agent_observation_without_accepting_research` |
| Research completes | Count is zero; Training Studio hands off to its next view, Infographic Studio offers the checked research | Session tests and both browser journeys |
| Training Studio starts building materials | Current work is the heading; next plan approval or available draft count replaces a moving ETA | Training Studio desk/page tests and building-status browser state |

Correction rounds retain the existing three-round bound, independent review and
source policy. A “Why another round?” disclosure shows the saved review reasons
as text. Live work and saved evidence are not restarted by this UI update.
Training Studio's live progress keeps the compatibility `minutes` field null;
it does not recalculate historical completion estimates while polling. Explicit
operation cost estimates and clearly labeled elapsed time retain their existing behavior.

## Saved files and compatibility

The helper's resumable case lives in `.studio-research/`. The consumer handoff is
`research/output.json`, `report.md`, `brief.md`, `evidence.md`, `facts.json` and the
pinned source captures. Artifact paths resolve relative to the manifest directory.
Native source folders retain their local-only sharing rules. Blog Studio's Team Hub
shares only the validated bundle's known output files and immutable captures as
part of its selected article, preserving cross-clone handoffs. Restoring
or moving a complete case must preserve them. Missing captures block verification
rather than silently counting as checked research on another computer.

The consumer checks owner `harness-research-synthesis`, schema 2, matching digest,
complete review state and every artifact hash. It also requires every source
snapshot in the manifest. Hashes establish saved integrity, not live website
currency or truth. Qualifications remain available to downstream authors.

Training Studio indexes schema-2 finding IDs directly for blueprint and brief
citation checks; it does not manufacture a legacy question record. Its traditional
`research-report.md` is still the approved readable copy. Presentation Studio
passes the authored brief and evidence relationships into outline authoring.
Blog Studio supplies the same brief and typed evidence to later writing jobs.

Earlier synthesis-driven browser runs use run schema 3, so older studio runtimes
refuse them rather than resuming through a legacy research adapter. A missing
research contract is rejected. Existing manual and queued research continues
through its old adapter. A run records the Harness Research version and digest it
started with. When Harness Research is updated before the run finishes, the studio
runs and verifies its research with the matching retained
`versions/<version>-<digest>` folder of the Harness Research installation; only when
that version is gone does it ask for it to be restored. Fresh
conversation workflows can explicitly import a complete synthesis case:

- Training Studio: `training.py research-import --case CASE`, then its normal
  research review. A page-driven training cannot be modified through this command.
- Blog Studio: `studio.py research import --id ID --case CASE`, then read the
  returned report and brief. This respects the blog's saved source policy.
- Presentation Studio: use the shared helper's `research_contract.py --case CASE
  --project DECK` to preserve the case and copy its reviewed bundle; record the
  completed research steps in the conversation's `run.json` as usual.

Imports preserve the actual review state and source captures. They refuse legacy
research conversion and do not grant approval or publication authority.

## What writers are told, comparisons and refresh

Every writer that receives reviewed research is told what it is, once, in
`research_contract.HANDOFF`: read its brief first, use the facts and findings to check
what is written, and never put an ID, digest or verdict in the words a reader reads.
`research_contract.purpose` builds each studio's purpose line; when the goal compares
options (compare, versus, vs, alternatives, choose between, which is better, or two named
options joined by "or"), it asks for a comparison with one criterion per row, saying where
something is unknown rather than absent. A word list can be wrong both ways, and then
costs one sentence.

A request to bring the research up to date sets `task['refresh']`, never a dossier field.
The author is then also handed the "Refresh selected evidence" section of Harness
Research's `synthesis-reuse.md` and asked to re-read each source, save new captures with
the date it read them, and update what changed. The review that follows is the whole
review, as Harness Research requires.

## Research stops and source boundaries

A complete bundle is shown as its authored brief first, the independent check's acceptance
and note, the gaps the findings and prose name (once each), partial-source limitations and
the number of supplied and public sources. Planning questions list their answering findings;
findings outside those questions appear under Also found. The full report and evidence stay
folded below. Version hashes remain internal to integrity and approval checks.

Planning questions have stable IDs. Harness Research is asked to name a finding after its
question, with `--` before the finding suffix, keeping the whole ID within 64 characters.
An exact question ID also matches; the longest match wins. A prefix without `--` does not.
One investigation answers at most eight planning questions together. Saved legacy queues
keep their separate brief and thirty-question limit.

A research-change request says before sending that it reruns the complete investigation
from the saved report, for up to three writing/checking rounds. It names the last try's
recorded time and money and the saved downstream work that will be made again. Missing
cost is described as unrecorded. Leaving findings out at Presentation Studio's Balanced
direction review instead redrafts the outline and looks without researching again; the
bundle stays intact and the saved selection controls what the outline may use.

Presentation Studio document research defaults to supplied documents only; public research
requires the explicit documents-and-web choice. Scratch research uses the public web.
Training Studio keeps its saved source scope. Supplied-only synthesis runs in both deck
studios write a plan from the form's optional questions (up to eight, 300 characters each),
or one question about the goal, without a planning assistant job. Step by step still reviews
that plan; Training Studio Balanced and Automatic accept it under the saved policy.
An explicit request to revise that plan uses the planning assistant with the current
questions and your request, keeping the supplied-only boundary and eight-question limit.

Blog Studio's step-by-step supplied-only runs use a claims map instead of synthesis research: one
worker lists the claims and exact passages in selected facts/material. Whitespace and line
breaks may differ; words may not. One correction is allowed, within the stage's time limit.
The map is handed to later stages without judging the author's claims. Balanced and
Automatic continue; Step by step reviews it. From-files supplied-only runs already read
the files at every stage and add no claims-map stage. Older saved pipelines remain intact.

A missing, changed or draft bundle never becomes an accepted account. The saved report
remains readable; unresolved research still blocks downstream jobs. An unread original
belongs to the blocked-research view: Harness Research cannot accept such a check.

Blog Studio claims maps read only ready factual references and material. Examples of a kind
of post and voice-only samples supply no claims; a new run without eligible material skips
the map. Changing a file’s role updates the start form’s predicted stops.

## Shared source picker and bounded collection

All four studios use Marketing Studio's shared source and progress component.
Add multiple public/Google links, PDF/DOCX/text/Markdown/HTML files, pasted text,
or a previously reviewed local report. Capture and preview read only those
selected sources. They never start an assistant, change Google documents, share
files or generate artwork. Supported files are limited to 8 MB apiece. Native
Google capture uses the existing account/defaults and retains only the chosen
content. A tab-specific Doc URL selects that tab; a full reference URL visibly
includes all tabs until the selection is narrowed. Missing tabs never fall back
to the whole document. Unsupported objects are disclosed as capture limitations.

“Search for additional external sources” starts unchecked. Approved sites remain
an optional stricter search boundary, including paths and redirects. A selected
URL is a reference, not permission to explore its links. Keep unreadable rows by
retrying, or explicitly remove/exclude them before starting. Source revisions and
bytes are checked again at start; unrelated ready sources survive a failed read.

New supported research runs use up to three investigators (one or two can be
chosen under Research options), then synthesis and a distinct independent review.
Every invocation has a host-issued identity. The pinned helper validates its
capture receipts and investigation packet, then assembles the evidence registry.
Checked areas survive a peer failure; prose correction reuses the registry and
located fact correction retries the affected area. An unchanged complete request
can resume without another assistant request. Changed sources, task permissions
or ownership cannot adopt an old or late response. A missing terminal observation
blocks a blind retry; a process cancellation request is never called confirmation.

Progress distinguishes elapsed time from observed active time and total assistant
time. Overlapping assistants do not multiply wall time, and missing cost remains
unknown. Native budgets reserve allowance across concurrent workers. The optional
Infographic Studio text research adapter keeps its existing 300-second per-call
limit and a 30-minute whole-request ceiling; it never invokes image tools.

Blog Studio proofreading and direct manuscript editing, existing presentation
editing, and supplied-only infographic planning remain outside research. Choosing
a previously reviewed report as reference preserves its purpose, evidence and
qualifications; research for another task is checked again. Explicit reviewed-case
handoffs support both legacy `research/` outputs and new topic-root outputs without
rewriting their reviewed bytes. Google/provider live acceptance is separate from
the synthetic suite and is not implied by its results.

New collection runs explicitly version their execution: Training Studio schema 5,
Presentation Studio schema 4, Blog Studio's saved runner schema 4 / desk-start
schema 2, and Infographic Studio's private research request schema 1. None of
these changes a saved serial run on resume. Source-backed Training Studio and
Presentation Studio starts save a private receipt before dispatch, so retrying
the same form after a lost reply reopens the existing item.
