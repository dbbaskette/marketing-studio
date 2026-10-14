# Guided blogs: page or conversation

Use this flow for a requested guided blog, stage approvals, or switching between
the page and chat. Focused edits, interviews and ordinary writing keep their
existing routes. Never start an approval pipeline just because a user asks for
a paragraph or draft.

`...` means `<python> <runtime>/studio.py --root <absolute-workspace>` as in
[workspace](workspace.md). Initialize a new workspace with `... init`.

## Start

For the page, run `... manage --open`. Keep that process running. The page's
**New blog** form selects the brief, sources, voice, research scope, assistant,
time limit and stop. It runs the assistant through each stage and waits for the
person's decision. Opening it does not turn on reference analysis.

For a conversation, gather title, audience, goal, selected sources and voice,
research scope and requested stop. Then use:

```sh
... run create --title "Title" --audience "Readers" --goal "Purpose" \
  --research supplied-only --stop package
```

Use `--research web-allowed` only for authorized public research, or `none` to
omit research. Add `--source <id>` for each chosen source and `--profile <id>`
for a saved voice, or `--tone "description"`. `--author` overrides a saved
default. `--stop` can be `outline`, `draft`, `review` or `package`. For an
existing article, use `--id <article-id>`; a saved manuscript starts at review.
This creates no model process in chat: you do the writing here.

## Each stage

1. Run `... run status --id <id>`. Read `next`, `stages`, `approval` and
   `expected`. Inspect the selected article, sources and voice using existing
   workspace helpers; retain originals and exact pins.
2. Load the relevant module from SKILL.md and write only that stage: research
   questions, research findings, outline, draft, review or export package.
   Research in chat follows the existing research/evidence workflow. Review
   must distinguish completed checks from assistant judgment and missing facts.
3. Save a temporary Markdown file outside the skill and submit it:
   `... run submit --id <id> --stage <next> --file <file> --expected <expected>`.
4. Show the saved document and limits, then wait for the person. Only their
   explicit approval authorizes `... run approve --id <id> --expected <latest>`.
   A request to make the whole blog does not approve individual stages.
5. For requested changes use `... run changes --id <id> --expected <latest>
   --request "Their request"`. Add `--stage draft` (or another earlier stage)
   to revise earlier work. Later decisions are invalidated and must be made
   again. Reload status before submitting the revision.

Never bypass the runner with an approval field in a document or a generic stage
edit. A stale document cannot be approved. A changed source pin needs explicit
reattachment; inspect and compare before replacing local work.

## Switch or resume

`... run list` finds guided blogs. Reload status before continuing. In page
approval mode the CLI refuses decisions and submissions: tell the person to
use that run's page. Do not ask for or extract its session key to decide for them.

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
