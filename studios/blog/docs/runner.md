# Write on the page or in a conversation

Blog Studio supports both. On the page it starts your selected Codex or Claude
CLI for each piece of writing, saves the result and waits for you. In a
conversation your assistant writes it with you. Both use the same blog folder,
stages and decisions.

## Open the page

Ask your assistant to **“Use Blog Studio. Open the page.”** Or, from a checkout:

```sh
python3 skills/blog-studio/scripts/studio.py --root "$HOME/blogs/.blog-studio" manage --open
```

Use Python 3.11 or newer. Keep the terminal open. The page runs only on this
computer, with a private session link; closing the browser does not stop work.
Stopping the terminal stops its worker. Reopening resumes runs you had enabled
on this computer, from their last saved stage.

## Your first blog

The page follows Training Studio’s current layout: **Home**, **Blogs**,
**Status** and **Settings**, with the same glass navigation and toolbar, progress
stages, paper documents and decision sheets. Home groups **Needs you**, **In
progress** and **Finished**. Settings saves writing defaults on this computer
for future page runs; existing runs keep their choices.

Choose **New blog** and work through three steps: topic and audience; mode and
voice; sources, assistant and limits. Choose **Write a blog**, **Outline only**,
**Revise a draft**, or **Review a draft**. Revision and review accept an uploaded
manuscript or a saved readable source; the original is retained. You can upload
references in the wizard too. The assistant receives only selected source and
voice context plus this blog's saved writing preferences, memories and explicitly
selected team context. Oversized context is refused rather than silently cut.

Choose selected sources only, sources plus public research, or no research. Pick
Codex or Claude Code, already installed and signed in, and a time limit for each
step. The runner uses your CLI account. It does not hold an API key. It has no
spending limit; your account's usage charges or limits still apply.

| It makes | You decide |
| --- | --- |
| Research questions, when research is chosen | Are these the right questions? |
| Research findings | Is the evidence sufficient? What is still unknown? |
| An outline | Is this the argument you want? |
| A draft | Does it say what you mean, in your voice? |
| A review | Which findings need changes? |
| An export package | Are the title, excerpt and handoff ready? |

Every row has a separate approval. Choose an earlier stage under **Ask for
changes** to revise the draft or outline after reviewing it. The later stages
are made and approved again. You can stop at outline, draft or review instead
of making a package. A saved draft can enter at review or revision. Review mode
keeps the manuscript as written; revision makes a new draft while retaining the
original.

**Blogs** shows all guided blogs and saved writing. Open a run to see steps and
made files. Each review page renders the saved Markdown as a paper document,
with **Checked for you**, **Worth a look** and **What changed** alongside it.
Comparisons use the exact last approved version. **Approve** opens a confirmation
sheet; **Ask for changes** lets you select an earlier stage. A finished or
paused run returns to **Resume** when you request a revision. A changed version
stays separate from the document you are reading until you choose to reload it.
The editorial pipeline, library, findings and memory tools remain available under
**Editorial tools** on Blogs.

Assistant notes are its judgment, not proof of completed checks. Public source
links and quoted claims need review: the browser runner does not independently
fetch and validate every citation. An approved review does not mark all existing
Blog Studio factual checks as passed.

**Pause after this step** lets the current job finish and prevents another.
**Stop** ends its process. Failed jobs retain previous writing and offer
**Try again**. No job automatically approves the result or publishes a blog.
One job works at a time in this workspace. Models can search the web only in a
public research job; they have no shell, file tools, connected apps or approval
tools. Only the runner saves their returned documents.

## In a conversation

Say **“Use Blog Studio. Make a guided blog about [topic], with approvals.”**
Your assistant asks for the brief, selected sources and voice, then makes each
stage and waits for your decision. Short requests such as “proofread this” keep
their existing focused workflow.

You can start in either place. **Run this from here** moves a conversation run
to the page. **Continue in the conversation** stops its browser worker and gives
you a request to paste into your assistant. The same files and decisions stay in use.
For an ordinary saved blog, open its details and choose **Run this blog**.

## Saved work and teams

Outlines and drafts remain `OUTLINE.md` and `DRAFT.md`. Research questions,
research findings, review and package live under `derived/`. The stage record
is `derived/blog-run.json`; earlier writing and decisions remain in history.
Changing an input or an approved document invalidates affected decisions.
An old page cannot approve a newer version. If someone edits while a worker is
running, that edit is kept and its late result is refused.
An edited saved document is never regenerated automatically. Choose **Review
this saved version** to bring your edit back for approval, ask for changes, or
continue in chat.

Runs use the existing selected Team Hub and its ordinary save, offline queue,
retry and conflict protections. Execution controls stay local and never travel
through the Hub. A checked-out run on another computer starts paused until a
person resumes it. There is no cross-computer runner ownership lease: run a
given blog on one computer at a time and reconcile competing revisions in chat.
Read-only Hub users can browse runs; page mutations recheck write access.

Google Docs imports, pushes, pulls and suggestions retain their existing explicit
chat commands. The package is a Markdown publication handoff, not a Google
transfer or a publishing action. The page does not change Google sharing.

## Verification

[Runner validation](runner-validation.md) records the state matrix, synthetic
checks and acceptance limits. [Hub acceptance](hub-acceptance.md) covers the
existing create/join, intake, saves, reviews and cross-clone protections.
