# Shared synthesis research

New browser runs use Harness Research's synthesis contract when the installed
helper supports it. Blog Studio, Presentation Studio and Training Studio share
`studio_core.research_contract`; they keep their own source permissions, worker
confinement, model profiles, stop controls and review levels.

The companion lock selects the stable **1.0.0** release at an exact commit and
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

The confined author invocation reads the helper's investigation, synthesis and
studio-handoff guidance. Its dossier includes an authored brief, typed findings,
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

New synthesis-driven browser runs use run schema 3, so older studio runtimes
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
