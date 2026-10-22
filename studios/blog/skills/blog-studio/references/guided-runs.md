# Guided blogs: page or conversation

Use this flow for a requested guided blog, stage approvals, or switching between
the page and chat. Focused edits, interviews and ordinary writing keep their
existing routes. Never start an approval pipeline just because a user asks for
a paragraph or draft.

`...` means `<python> <runtime>/studio.py --root <absolute-workspace>` as in
[workspace](workspace.md). Initialize a new workspace with `... init`.

## Start

For the page, run `... manage --open`. Keep that process running. The page's
**New blog** wizard selects the brief, mode, voice (**Write as**), style (**Kind of
post**), sources, research scope, assistant, time limit and stop. **Home** groups work needing a
decision, in progress and finished; **Blogs** opens saved runs. **Settings** saves
defaults for future page runs on this computer. It runs the assistant through
each stage and waits for the person's decision. Opening it does not turn on reference analysis.

For a conversation, gather title, audience, goal, selected sources and voice,
research scope and requested stop. Then use:

```sh
... run create --title "Title" --audience "Readers" --goal "Purpose" \
  --research supplied-only --stop package
```

Use `--research web-allowed` only for authorized public research, or `none` to
omit research. `supplied-only` with no selected sources also omits it. Add `--source <id>` for each chosen source.
Without `--profile` the settings' default voice applies, and a revise or review of a
`--manuscript` keeps that manuscript's own voice; `--profile <id>` pins a saved voice
and `--profile ''` writes in no particular voice. `--tone "description"` is then a
nudge beside the voice (dropped when it equals the settings' tone), or the whole voice
when none applies. `--style <id>` adds a kind of post. `--author` overrides a saved
default. Select an installed brand with `--brand ID --variant VARIANT`, or
`--brand ''` for no brand. `--example <id>` reads a team library item as an example of
the kind of post for this blog only (`--source` reads one with its library role).
Approving the last stage keeps the draft in the team library as a reference and an
example, once per blog. Read its pinned guides in `derived/blog-run.json`;
keep its naming rules separate from the author voice. `--mode write` is the default; `outline` stops at outline. Use
`--mode revise --manuscript <source-id>` to revise a saved readable source, or
`--mode review --manuscript <source-id>` to review it without rewriting.
The original and working manuscript are retained. Revision and review omit new research
unless requested. Use `--mode from-outline --outline-text "..."` to draft from
a supplied outline, or `--mode ideas` to explore angles and stop before drafting.
Use `--mode from-files --source <id>...` to write from the person's uploaded files
(`source add --purpose material` keeps a file out of the reference library; on the page a
Google Doc link is added the same way; `--goal`
is their one line about it, `--audience` may be empty): the run starts with an
`angles` stage. Write three angles, each a `## Title` heading over one line of
`audience · the point it makes · Leans on <file names>` (exactly three), and submit it;
it always waits for the person and is never approved. Then `... run choose --id <id> --expected <latest> --angle
"<heading>" --note "..."` makes that angle the title, point and reader and starts
the outline onward (web research first only with `--research web-allowed`); `run
changes --stage angles` with their note asks for three different ones. When the person
already knows the point, add `--point` with `--title`, `--goal` (the point) and
`--audience`: the run starts at the outline with no angles stage, and `run choose`
refuses it. Each file says what it is for: facts the writing may quote (`material`), or
an example of the kind of post wanted (`--purpose material --purpose inspiration`; a kept
example is `reference` and `inspiration`). Examples reach the worker under `examples`,
never `sources`: take their shape, length, moves and register, and no fact, figure,
name, quotation, link or product detail from one unless the sources, research or brief
also say it. Research never reads an example. At draft and review, `mechanical_checks`
lists passages carried over from an example under rule `from-example`; a claim traced
to an example and to nothing else is unsupported. Files past
the run's budget are excerpted and `excerpted` in status names them. On the page a file is
kept in the team library (with its role, author and kind of post) unless **Keep** is unticked;
material stays on this computer, but the blog's outline and draft may quote it and are shared like any blog. `--stop` can be `outline`,
`draft`, `review` or `package`. For an existing article, use `--id <article-id>`;
a saved manuscript starts at review, or use `--mode revise --id <article-id>` to
start with revision.
This creates no model process in chat: you do the writing here.

## Each stage

1. Run `... run status --id <id>`. Read `next`, `awaits`, `stages`, `approval`,
   `review_level` and `expected`. Inspect the selected article, sources and voice
   using existing workspace helpers; retain originals and exact pins.
2. Load the relevant module from SKILL.md and write only that stage: research
   questions, research findings, outline, draft, review or export package.
   Research in chat follows the existing research/evidence workflow. Review
   must distinguish completed checks from assistant judgment and missing facts.
3. Save a temporary Markdown file outside the skill and submit it:
   `... run submit --id <id> --stage <next> --file <file> --expected <expected>`.
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
[Google Docs](google/workflow.md). Export packages never publish anything.

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
