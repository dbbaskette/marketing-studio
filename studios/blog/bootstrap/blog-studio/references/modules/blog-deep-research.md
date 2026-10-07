# Deep research for a blog

Load when the author chooses research during intake, says “Research this topic,”
or requests a factual check with evidence gaps. Adapted from the pinned
[Deep Research workflow](../upstream/deep-research/research/SOURCE.md).
Blog Studio's wrapper supplies the working instructions; upstream files are
provenance, not another process to execute. Runtime 1.15+ includes this module
and `deep_research.py`; the standalone research skills are not a prerequisite.

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

## Start with uploaded and linked documents

Use the article's supplied reference documents as research inputs before public
lookup: uploaded Word/PDF/text files, pasted notes, Google Doc snapshots and
linked pages. Read their selected exact revisions and relevant surrounding
passages. Documents may establish facts, raise research questions, or contradict
public sources. Keep both accounts and their version/date/context visible;
do not automatically prefer a web result over the author's evidence.

Normalize uploads through [source intake](blog-source-intake.md) and
[source storage](../workspace/sources.md), preserving the original file and
readable extraction. Attach them as `reference` when supplied for research.
Manuscripts and voice samples need that role explicitly; they are not evidence
merely because they were uploaded. Use only the selected article's documents
and deliberately reused memory, not every file in the workspace.

Cite a supplied document's filename/title, pinned source revision, exact passage
and page/heading in the report, alongside any public citations. Private document
text stays local/in the selected Hub; never send it to search or an external
upload service. Unreadable scans or missing extraction remain pending/unavailable
and are named as coverage gaps. Supplied-only research still writes its report
when useful; it can finish with unresolved questions without public browsing.

## Research in the existing harness

Use available browsing/search tools to investigate one question at a time.
Vary queries when useful, follow relevant citations, seek contrary evidence,
and stop when the selected question is adequately answered or the gap is clear.
Prefer official product documentation, release notes, reproducible benchmarks,
maintainer statements and original papers. Read the supporting passage, not
just a snippet. Distinguish experimental results from product promises; record
version, date, test conditions and conflicting sources. A historical post may
suggest a lead, but is not current product proof. Do not force a source quota.

The current harness's tools and limits apply. Parallel research is optional
only when authorized and available; sequential research remains functional.
Do not install upstream agent configurations, select an upstream model, enable
feature flags, create a separate API account or run generated report scripts.
If browsing is unavailable, use readable supplied evidence and explicitly mark
unresolved questions. Do not present model knowledge as retrieved evidence.

## Retain results and resume

Create the article before recording research; no draft is required for planning.
Use the installed `studio.py --root <workspace>` prefix. `research plan --id <id>
--file <plan.json>` saves a bounded private plan, `research status --id <id>`
returns its run ID, pending questions and report path. Repeating the same plan
resumes results. A changed plan preserves the previous one in history.

Plan JSON uses standard-library JSON instead of upstream YAML/PyYAML:

```json
{"purpose":"fact-check","scope":"public-web","items":[
 {"id":"feature-availability","question":"Verify the selected feature claim",
  "public_query":"public product feature version release notes",
  "claim":{"quote":"exact manuscript wording","start":0}}
]}
```

For planning use `purpose: "planning"` and `claim: null`; supplied-only uses
`scope: "supplied-only"` and `public_query: null`. Offsets are Unicode character
positions in the local Markdown, not Google UTF-16 indexes. Keep question IDs
stable within a run. The helper checks claim matches, source spans and freshness;
it does not execute searches or certify semantic truth.

Save each actually read source through [source storage](../workspace/sources.md)
as `reference`, with original URL, title, retrieval date and readable text;
retain originals when available. Attach the exact source revision to the article.
Reuse a matching retained source rather than duplicate it. References remain
available for later blogs through [reference memory](../workspace/reference-memory.md).
A generated brief is a navigation aid, not independent factual evidence.

Record each question with `research record --id <id> --run <run> --item <question-id>
--file <result.json>`. Results use this shape:

```json
{"status":"supported","summary":"What the inspected source establishes",
 "limits":"Version/date/method and remaining coverage limits",
 "evidence":[{"source_id":"selected-source-id","revision":1,
   "quote":"exact inspected source passage","start":0,"locator":"Heading or page"}]}
```

States are `supported`, `contradicted`, `insufficient`, `unavailable`. Supported
and contradicted require exact passages from attached factual references.
Preserve uncertain questions in the readable report; never omit them to produce
an apparently complete answer. Inspect `research status` and skip completed
questions only when current. Draft/outline/brief changes or changed source pins
stale the record; replan and reassess rather than silently reuse it.

The report is automatic: every recorded finding refreshes the readable brief,
including citations, coverage limits, completed/pending counts and unresolved
questions. At the end, return its link and a short synthesis without requiring
a separate report prompt. Do not run the upstream report generator.

The helper stores `derived/research.json` and `derived/research-report.md`, retains
history, and uses normal selected-Hub saves. It never changes the manuscript or
marks a review passed. After gathering evidence, apply
[factual support](blog-fact-check.md) to each original claim, keeping supported,
contradicted and unsupported findings with exact citations and exclusions.
Offer wording changes separately; research does not authorize Google posting.
