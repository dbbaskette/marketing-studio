# Deep research for a blog

Load when the author chooses research during intake, says “Research this topic,”
or requests a factual check with evidence gaps. The `harness-research` skill does
the research, as it does for Training Studio and Presentation Studio, through the
same shared research component (`scripts/studio_research/`). Blog Studio hands it the
article's plan and references and keeps its own rules around it.

If `harness-research` is not installed, stop here and point to
https://github.com/dbbaskette/harness-research-skill: the installer brings it
(`installer/install.sh --companions install`). Nothing else may stand in for it.

## Select questions and scope

For a new blog, offer once: **use supplied sources**, **research the topic**, or
**proceed with open questions**. Infer the answer from the author's request;
skip the choice when they already chose. Respect outline-only and interview
stop points. Never start research during a simple proofread or voice edit.

For fact-checking, inspect the current manuscript and selected references first.
Extract material claims: versions, availability, capabilities, comparisons,
performance numbers and causal assertions. Group related gaps into focused
questions; prioritize claims that would change the reader's conclusion. Reuse
current exact evidence instead of researching everything again. “Fact-check”
authorizes this bounded research prerequisite; a supplied-only policy stays in
force. Do not fetch more sources when the author limits the source set. Record
“Use only my sources” with `article research-policy --id <id> --policy supplied-only`;
change it to `web-allowed` only when the author explicitly permits outside research.

When research scope is unresolved, offer these two choices once:

| Choice | What happens |
| --- | --- |
| **Uploaded sources only** | Read the selected uploaded/supplied documents and retained references. Make no new external searches, fetches or uploads; report gaps. |
| **Uploaded sources plus external research** | Read those documents first, then look up public evidence for gaps and contrary findings. Cite both. |

Save the first choice as `supplied-only`, the second as `web-allowed`, using
`article research-policy`. Reuse it for research and fact-checking this blog.
Explicit wording such as “Research uploaded sources only” or “Research uploaded
sources plus external research” selects the mode directly; do not ask again.
For an unspecified request, ask the two-option question before external lookup;
reading local selected documents can proceed while awaiting the answer.
“Use only my sources” and “Use uploaded sources plus external research” can
change a saved choice. Do not broaden scope merely because evidence is missing.

Keep the claim quote and its manuscript character offset local. Form separate,
generic public queries from established public product names/concepts/versions.
Apply [privacy](../privacy.md) before each external query; never copy a private
claim, title, customer name, internal URL or draft into search. A null public
query means local/supplied evidence only. The helper rejects obvious URLs/paths
but cannot classify confidentiality; the harness must review the actual query.
If a safe question cannot be formed, record the gap rather than disclose it.

## Attach references before planning

Research cites the references it was planned with. Attach every supplied
document the research should use as a `reference` **before** saving the plan:
uploaded Word/PDF/text files, pasted notes, Google Doc snapshots and linked
pages, normalized through [source intake](blog-source-intake.md) and
[source storage](../workspace/sources.md) with the original file kept.
Manuscripts and voice samples need that role explicitly; they are not evidence
merely because they were uploaded. Use only the selected article's documents
and deliberately reused memory, not every file in the workspace.

Saving the plan writes a readable snapshot of each attached reference to the
article's `research/sources/` folder for harness-research to read. Those
snapshots stay on this computer and are written again from the shared
references wherever the article is opened. A reference attached after the plan,
or a newer revision of a planned one, needs the plan saved again; the helper
says so. Private document text stays local or in the selected team workspace;
never send it to search or an external upload service. An unreadable reference
is listed as a coverage gap.

## Research with harness-research

Load the `harness-research` skill and follow its guidance for investigating:
one question at a time, the supporting passage rather than a snippet, contrary
evidence, version, date and test conditions, and no source quota. Its
[evidence contract](https://github.com/dbbaskette/harness-research-skill) is the
one every studio uses. Intake here is settled: do not ask the author again about
scope, sources or purpose. Do not present model knowledge as retrieved evidence.

Save through Blog Studio, not the harness-research helper directly, so the
article's policy, references and claims are checked. Use the installed
`studio.py --root <workspace>` prefix:

- `research plan --id <id> --file <plan.json>` hands the plan to harness-research.
  Repeating the same plan resumes it. A changed plan starts a new run; questions
  defined exactly as before keep their findings when the topic, scope, sources
  and inputs are unchanged, and harness-research keeps earlier runs in history.
- `research record --id <id> --run <run> --item <question-id> --file <result.json>`
  records one finding as soon as it is assessed.
- `research status --id <id>` returns the run, pending and unresolved questions,
  stale evidence, coverage gaps and the report path.

Plan JSON:

```json
{"purpose":"fact-check","scope":"public-web","items":[
 {"id":"feature-availability","question":"Verify the selected feature claim",
  "public_query":"public product feature version release notes",
  "claim":{"quote":"exact manuscript wording","start":0}}
]}
```

For planning use `purpose: "planning"` and `claim: null`; supplied-only uses
`scope: "supplied-only"` and `public_query: null`. Offsets are Unicode character
positions in DRAFT.md, not Google UTF-16 indexes. Keep question IDs stable.
BRIEF.md, OUTLINE.md and DRAFT.md are pinned; changing one makes the research
stale until the plan is saved again.

Result JSON:

```json
{"status":"supported","headline":"One line giving the answer",
 "summary":"What the inspected source establishes",
 "limits":"Version/date/method and remaining coverage limits",
 "evidence":[{"source_id":"attached-source-id","revision":1,
   "quote":"exact inspected source passage","start":0,"locator":"Heading or page"}]}
```

States are `supported`, `contradicted`, `insufficient`, `unavailable`;
`headline` is optional. Supported and contradicted require exact passages from
attached factual references. Save each public source actually read through
[source storage](../workspace/sources.md) as a `reference` with its original URL,
title, retrieval date and readable text, attach it, and save the plan again
before citing it. Preserve uncertain questions in the report; never omit them to
produce an apparently complete answer.

## Guided runs on the page

A guided run researches the same way. Its research-questions stage drafts the
plan as JSON (`{"topic", "items": [{"id", "question", "public_query"}]}`), saved
as `research/plan.json` and shown as `research/plan.md`. Its research stage gives
each pending question one worker with the shared research tools (read and search
the article's references, save a public page only when the article is
`web-allowed`, hand back one checked finding), records each finding as it is
accepted, and shows `research/report.md` at the gate. A question with no finding
after three tries is recorded as unavailable. Handing in the research stage in
chat needs a current finding for every question, recorded as above.

## The report and after

harness-research keeps the record in `.harness-research/research.json` and
refreshes `.harness-research/research-report.md` on every save, with citations,
coverage limits, counts and unresolved questions; `research/report.md` is the copy
the research gate shows. Before handing research on,
run `research status`, open the report and confirm no question in scope is
pending. Return its link and a short synthesis. Research saved by Blog Studio
before it used harness-research is reported stale; plan it again.

Research never changes the manuscript or marks a review passed. After gathering
evidence, apply [factual support](blog-fact-check.md) to each original claim,
keeping supported, contradicted and unsupported findings with exact citations
and exclusions. Offer wording changes separately; research does not authorize
Google posting.
