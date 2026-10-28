# Saved step-by-step Blog Studio work

This compatibility path continues blogs already saved with `derived/blog-run.json`.
New work uses [conversation desk commands](conversation-desk.md); `run create`
refuses with those commands. Opening saved work preserves its existing pins,
decisions and approval rules. Do not duplicate or automatically migrate it.

`...` means `<python> <runtime>/studio.py --root <absolute-workspace>`.

## Each stage

1. Run `... run status --id <id>`. Read `next`, `awaits`, `stages`, `approval`,
   `review_level` and `expected`. Inspect the selected article, sources and voice
   using existing workspace helpers; retain originals and exact pins.
2. Load the relevant module from SKILL.md and write only that stage: research
   questions, research findings, outline, draft, review or the handoff.
   Research in chat follows the existing research/evidence workflow. Review
   must distinguish completed checks from assistant judgment and missing facts.
3. Save a temporary Markdown file outside the skill and submit it:
   `... run submit --id <id> --stage <next> --file <file> --expected <expected>`.
   A draft or handoff carries no source IDs or editorial placeholders; add one
   `--gap "..."` for each thing the author must supply before publishing.
4. Read `awaits` in the returned status. `submission` means the review level
   accepted that stage (its row shows `auto_accepted`): do not approve it, and
   write the next stage. The default Balanced level waits for the person only at
   the first writing stage (the outline, or the draft when the run has no outline
   stage: a run from an outline, a revision, or an existing blog after changes to
   its draft) and the final stage; Automatic draft only at the final stage;
   Step by step at every stage. A run that selected an inspiration source before
   examples were separated goes stale, since its input pins change. `decision` means show the saved document, any
   stages accepted since the last decision, and their limits, then wait for the
   person. Only their explicit approval authorizes
   `... run approve --id <id> --expected <latest>`. A request to make the whole
   blog does not approve individual stages.
5. For requested changes use `... run changes --id <id> --expected <latest>
   --request "Their request"`. Add `--stage draft` (or another earlier stage)
   to revise earlier work. Later decisions are invalidated and must be made
   again. Reload status, then write the revision as a [minimal edit](minimal-edits.md)
   of the saved document before submitting it.

Never bypass the runner with an approval field in a document or a generic stage
edit. A stale document cannot be approved. A changed source pin needs explicit
reattachment; inspect and compare before replacing local work.

## Switch or resume

`... run list` finds guided blogs. Reload status before continuing. In page
approval mode the CLI refuses decisions and submissions: tell the person to
use that run's page. The page renders each saved document, shows its file/input
checks and assistant notes, and compares revisions with the last approved version. Approve
opens a confirmation sheet; it never approves merely by opening the document.
Do not ask for or extract its session key to decide for them.

From chat, `... run handoff --id <id> --expected <latest>` moves decisions to
the page, paused until the person presses **Resume** there. **Run this from
here** on a chat run also moves it to the page. **Continue in chat** on a page
run stops its worker and returns decisions to this conversation. Reopen status
and use the same article; do not create a duplicate.

The run and its decisions are ordinary files with the blog and travel through
the existing Hub. Automatic execution is local to the computer where the person
started it. After another clone checks it out, press Resume explicitly. Avoid
running the same blog simultaneously on multiple computers; the Hub retains
competing revisions for reconciliation. Google transfers remain explicit via
[Google Docs](google/workflow.md). The handoff never publishes anything.

## When a page run stops

`run status` says why: `reason` is `cli` (check the assistant under **Status → Check
this computer**), `time-limit` (the blog's step limit, raised by **Try again with more
time**; Settings changes it for new blogs) or `research-check`. `said` holds the last
lines the CLI printed, redacted and without the job's own text, kept on this computer
only; do not copy them anywhere shared.
Research that stops before its check accepts it is kept in the blog's
`.studio-research-draft`, never shared, and only while its inputs and research version
hold (any saved research lets it go); `research.refusal` groups the check's objections
by kind and verdict, and `research.last` says what the attempt took (tokens and dollars
only where the CLI reported them). **Try again** continues from that draft for up to
three more rounds. **Continue without research** on the page drops the research stages;
later stages then get `research_policy: none` and no `research_bundle`, and status
shows `research_skipped`. **Finish**
always asks first and keeps the draft in the team library.

## Manuscript editing on the page

**Edit manuscript** supports local Markdown edits, scoped checks, selected findings,
and explicit Google suggestions/comments delivery. Opening a Google Doc goes there
after preview. Preserve the original author voice; selected replacements can be
applied locally before delivery. Each send is previewed and revision-checked through
the same Google review helpers as the CLI. Conflicts remain local until reconciled.

## Research stops and supplied material

Saved runs from your documents only, with selected facts/material, map the claims in that material
instead of running research. Each claim names a source ID and an exact passage. The runner
checks words against that source (ignoring whitespace and line breaks), allows one
correction and stops on another failure. Later writers receive the map and keep the
claims within what the material says. Balanced and Automatic continue to the outline;
Step by step reviews the map. Continue without research drops this stage too.
From-files runs from your documents only are unchanged: their files are read at every stage.

Research from your sites or the web searches the sites first (`site:` queries) and
saves a page only under them unless the web is chosen; a refused page, redirects
included, becomes a source limit naming the sites. It uses a separate tool-less plan with at most eight questions, investigated
together and checked independently. The research review leads with the authored brief,
checker's note, gaps, source limitations and findings mapped to questions. Report and
evidence are folded below. Ask for changes says before sending that the full research
runs again, what its last try recorded and which saved later stages it will make again.
Saved older runs continue through their original research pipeline.

## Review and finish on the page

Developing an idea includes review and handoff. The review aside opens by default and remembers the person's choice per blog. Its checks come from the current draft: voice rules, repeated paragraphs and openings, example carryover and preservation findings, rather than a generic assurance.

**Apply the review's findings** confirms a new draft, review and handoff pass, preserves the previous draft and revisions, and sends the complete saved review with the minimal-edit instructions. The review is `derived/blog-review.md`. Done offers pre-publish checks, repurposing and a private Google Doc handoff. See [page tools](page-tools.md) for the latter's revision and retry rules.
