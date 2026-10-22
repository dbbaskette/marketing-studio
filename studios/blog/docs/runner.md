# Write on the page or in a conversation

See [the manuscript workflow](manuscript-workflow.md) for focused editing, supplied
outlines, idea development, and selected Google suggestions or comments.

Blog Studio supports both. On the page it starts your selected Codex or Claude
CLI for each piece of writing, saves the result and waits for you. In a
conversation your assistant writes it with you. Both use the same blog folder,
stages and decisions.

## Open the page

On a Mac, double-click **Open Blog Studio.command** in your home Applications
folder. On Mac or Linux, run the installed command:

```sh
sh ~/.local/share/blog-studio/studio
```

It finds a supported Python and opens the page. It starts with
`~/blogs/.blog-studio`, or the workspace you last chose with
`sh ~/.local/share/blog-studio/studio --root <absolute-workspace>`.

You can also ask your assistant to **“Use Blog Studio. Open the page.”** From a
source checkout, the Python entry point remains available:

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
progress** and **Finished**. Settings edits shared values for all studios and local writing preferences for
future blogs; existing runs keep their choices. **Status → Check this
computer** shares setup’s read-only checks and next steps. You can run the same
report with `sh ~/.local/share/blog-studio/studio check`.

Choose **New blog**, pick a task, and work through two steps. **Your brief** asks for
the topic and reader, **Write as** (your default voice, another saved voice, no
particular voice, or **Learn a new voice…**) and **Kind of post** (a starter or
learned style: the shape of the piece, while the voice is how it sounds). A
manuscript keeps its own voice unless you pick one. **Start writing** adds optional
sources and research, and **Tone, author and brand**; the tone is a nudge on top
of the voice. Choose **Write a blog**, **Outline only**,
**Revise a draft**, or **Review a draft**. Revision and review accept an uploaded
manuscript or a saved readable source; the original is retained. You can upload
references in the wizard too. The assistant receives only selected source and
voice context plus this blog's saved writing preferences, memories and explicitly
selected team context. Oversized context is refused rather than silently cut.

Voices and styles are described in [their own section](#voices-and-styles). A run's
**About this blog** shows its voice and kind of post.

## Start from a Google Doc

Choose **Open Google Doc** on **Home**, **Blogs**, or in the new-blog wizard.
Paste the manuscript's Google Doc link or ID, then choose **Preview Google Doc**.
The page uses the workspace's remembered Google account, or the active Google
Cloud CLI account. Google Cloud CLI must already be installed and signed in with
Drive access; see [Google setup](google-docs.md#local-codex-and-claude-gcloud-setup).
Preview reads only the selected Doc and saves a private capture on this computer.

Read the text and structure summary and compare them with the original Doc.
Images and their encoded data are omitted from previews; inspect them in the
original Doc. Saved originals, drafts, formatting history and downloads retain them.
Pending suggestions stay in Google and are excluded from the imported text.
Confirm the preview and choose **Import and continue**. Blog Studio saves the
original, draft and formatted history and links that same Doc as the working copy.
With a selected team workspace or Team Hub, the imported blog follows its normal
sharing settings; raw Google data and unconfirmed previews stay on this computer.

Import opens **Edit manuscript**. Make local edits or select a focused check without
starting a new-blog wizard. No assistant starts until you request an editing action.
If the Doc is already linked here, Blog Studio opens its existing run or saved
blog without replacing local edits or its Google baseline. The working Doc link
remains visible in the wizard and writing run.

The page imports a single-tab Doc. Access failures, multiple tabs or an unreadable
capture leave saved blogs intact. You can retry, or upload a downloaded manuscript.
Reviewing and revising on the page saves local work. Select suggestions or comments,
preview the target document, and explicitly confirm delivery from **Edit manuscript**.
The CLI remains available for Google reconciliation and advanced operations.

## Your brand skill

Open **Settings → Brand skill**, as in Training Studio. A brand skill belongs to
your organisation and is supplied separately. You can write without one.

- **Its repository** takes an https or ssh address that Git can access with your
  existing sign-in. **Which release** takes a tag such as `v1.4.0`; leave it empty
  for the newest. **Check and save** reads release tags before saving anything.
  A failed check preserves the previous settings. Clear both fields to forget
  the repository; installed skills stay installed.
- **Use this brand skill** lists skills found in the usual shared install and
  assistant skill folders, following Training Studio's discovery rules.
  `BRAND_SKILL_RUNTIME` can point to a particular installed skill folder.
  Choose one and press **Use this skill**. The choice stays on this computer.
- **Install the brand skill** or **Install selected release** opens a sheet with
  the repository, tag and commit. Nothing is downloaded or installed until you
  choose **Install it now**. Only install from a repository you trust.
  Installation is refused while a blog is working and blocks new writing jobs until
  it finishes. Home and Status show its result. Use **Check and save** again to
  check for another release.

The install uses the release's own installer, with the same ZIP/checksum or
tag-clone protocol as Training Studio. It rechecks that the tag still points to
the commit shown. Research installation is skipped. If the release declares it
would install or replace another companion, Blog Studio refuses before running
the installer; install a compatible companion yourself first.

In **New blog → Its shape → Brand**, select a brand and variant from that skill,
or **No brand**. A shared `brand.brand` / `brand.variant` default is offered when
the selected skill has it. The blog exports a contract for the `blog` medium
and keeps its exact naming and design guides with the run. Existing blogs keep
that contract when settings or installed skills change, including when resumed
on another computer. Brand naming rules and visual guidance stay separate from
the author's voice; a logo or palette does not imply a company tone.

The brand repository, release and identity live in the shared settings file.
Installed skill paths and release-check observations stay in Blog Studio's local
data folder. Only the selected contract travels with a blog.

## Voices and styles

A **voice** is how one person sounds; a **style** is the shape of a kind of writing,
such as a product announcement or a how-to. A blog takes one of each: the style decides
the structure, the voice decides the wording. In **New blog** they are **Write as** and
**Kind of post**. Open **Tools → Voices and styles** from a blog, or from **Library and
team tools** and **Settings**.

**Write as** offers your default voice, another saved voice, no particular voice (the
tone you describe), or **Learn a new voice…**. A manuscript you revise or review keeps its
own voice unless you pick one, and **New blog from my files** offers the same **Write as**.
Your personal default voice is pinned at the revision it names. The tone you give is kept as a nudge beside a voice, unless it is just your
usual default. **Change the voice** on a blog switches its voice for what comes next;
it asks once when the blog already has writing, since its reviews will need a new look.
Nothing is rewritten, and the blog's history records the change.

A voice belongs to one author, and that author need not be you. If you ghostwrite, learn
a voice for each person you write for, from their published posts, and start a blog with
that voice and, under **Tone, author and brand**, their name. Each voice sample records
whose writing it is, and the sheets ask before reading anything.

Blog Studio ships eight starter styles for tech-industry writing: product announcement,
release notes and changelog, technical deep dive, how-to and tutorial, point of view,
customer story, comparison and evaluation guide, and postmortem and lessons learned.
They are confirmed and ready to choose from the start. A starter is copied into your
workspace only when you edit it, retire it or use it for a blog; you can also export
it. **Learn a style from examples** reads examples of a kind of writing by anyone and
proposes a guide, which stays provisional until you confirm it.

Voices are learned from writing the author wrote. Bring samples in four ways:

- **Upload an authored sample**, naming the author.
- **Use as a sample.** A source already in your reference library becomes a voice
  sample, with the author named; **Use as an example** does the same for a style.
- **Import a LinkedIn export.** On LinkedIn, open Settings & Privacy, Data privacy,
  then Get a copy of your data; choose Profile and Articles and wait for the email.
  Choose the downloaded zip in the sheet. Only `Profile.csv` and the articles are
  read: the person's name becomes the author, their headline and About text become
  author background, and each article a voice sample. An export is usually your own;
  when a colleague hands you theirs, give their name in the sheet. Nothing signs in
  to LinkedIn, and connections or messages are never read.
- **Add links to posts.** Paste links, or choose a text file with one link per line;
  the author is suggested from the file name and you can change it. Blog Studio first
  shows what it will do: the site, the links already in your library and the ones it
  will fetch. It then reads each new page once, in batches, and saves it in your
  reference library under "Published posts by" the author. A post whose byline names
  someone else is left out unless you keep it; a kept post keeps its published byline.
  Failed links can be tried again without fetching the rest. LinkedIn pages cannot be
  read this way; use the export.

**Add links to examples** does the same for a style, without the byline check. From a
terminal, `library voice-links` does the same work; see
[commands](commands.md).

Every sample is a source in your reference library, so it follows the same sharing rules
as any other source. Learned voices and styles stay provisional until you confirm them,
and an existing blog keeps the revision it was started with.

## Run and review

Choose selected sources only, sources plus public research, or no research.
Selected sources only, with no sources selected, skips the research steps. Pick
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

How often you decide depends on the shared **Review level** in **Settings**; a
run keeps the level it started with. The default, **Balanced**, stops for you
twice: at the outline, with the research questions and findings beside it, and
at the run's last step (the export package or your chosen stop), with the steps
since the outline beside it. The steps between continue on their own; Blog Studio
records that the review level accepted them, never that you approved them.
**Step by step** stops at every row, and **Automatic draft** only at the last
step. Without an outline, as when revising a draft, Balanced also stops only at
the last step.

Choose an earlier stage under **Ask for changes** to revise the draft or outline
after reviewing it, including one the review level accepted. The assistant edits
that saved document, changing only what you asked. The later stages are made
again and reach you at their usual stops. You can stop at outline, draft or
review instead of making a package. A saved draft can enter at review or
revision. Review mode keeps the manuscript as written; revision makes a new draft
while retaining the original.

**Blogs** shows all guided blogs and saved writing. Each card has **Delete**,
which asks for the blog's title, stops anything running for it and keeps it for
30 days under **Recently deleted**, where **Restore** brings it back. Open a run
to see steps and made files. Each review page renders the saved Markdown as a
paper document, with **Checked for you**, **Worth a look** and **What changed**
alongside it.
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
**Try again**, which makes that step again in a new job. No job approves its own
result or publishes a blog. **Finish**, at the last step, always opens its
confirmation, whatever the review level: it approves the shown version and keeps
the draft in the team library as a reference and an example of its kind of post.

A stopped run says what to do next beside the error:

- **A CLI failure** names **Status → Check this computer** and offers **Open
  Status**. **What the assistant said** shows the last 20 lines its command printed,
  kept in `.blog-runs/diagnostics/cli` on this computer only, and replaced by the
  next job.
- **A step out of time** says it ran out of the time a step may take, with this
  blog's minutes. The limit is in **Settings → Step time limit** for new blogs;
  **Try again with more time** doubles it for this one.
- **Research** says its round while it works ("Round 2 of 3, the independent
  check"); each job's seconds are kept with the run on this computer, and its tokens and cost where
  the CLI reports them (Claude Code does; Codex, as Blog Studio runs it, does not).
  Research that stops before its check accepts it is kept in the blog's
  `.studio-research-draft` folder, which the Team Hub skips and a shared studios
  repository ignores. A refusal lists **What the research check objected to**,
  grouped by kind and verdict with the first note of each. **Try again** continues
  from the kept draft for up to three more rounds, within the step's limit, and says
  what the last attempt took. **Continue without research** takes the research steps
  out of the run, with a confirmation; the outline and later steps then work from the
  brief and selected sources alone.

First-run setup opens **Writing preferences**, and an assistant that is not
installed is marked "Not installed — see Status" there and on the start form.
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

## Shared studios repository

Join from **Settings** or **Status**. The page switches to its own team clone.
Blogs have one driver, with **Take this blog**, **Take over**, **Hand over**, and
numbered **Publish revision** controls. **Share now** retries pending decisions.
See [team workspaces and migration](team-workspace.md) and the
[shared studios settings](shared-studios.md). Settings saves shared values to
that file directly, with no local override or additional consent toggle. Missing
or unreadable shared settings use built-in defaults; writing remains available.
Legacy local copies migrate only to missing shared members, then are removed.
An existing shared value is kept and reported. An unreadable file is preserved
and shared-value saves are refused until it can be read.

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

Google Docs imports and selected suggestions/comments are available on the page;
advanced pushes, pulls and reconciliation retain their existing explicit chat commands. The package is a Markdown publication handoff, not a Google
transfer or a publishing action. The page does not change Google sharing.

## Verification

[Runner validation](runner-validation.md) records the state matrix, synthetic
checks and acceptance limits. [Hub acceptance](hub-acceptance.md) covers the
existing create/join, intake, saves, reviews and cross-clone protections.
