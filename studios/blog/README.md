![Blog Studio: bring material, write on the desk, review suggestions and send when ready](docs/assets/blog-studio-header.svg)

# Blog Studio

Turn ideas, notes and rough drafts into blogs that sound like you. Start a new
piece or bring an existing draft, including a Google Doc. Write with your signed-in
Codex or Claude Code assistant, then read, edit and finish on one writing desk.

Use Blog Studio independently or from [Marketing Studio](../../README.md). Google
Docs and team sharing are optional; you can write entirely in a local workspace.

[Install Blog Studio](#install-blog-studio) · [Start your first blog](#start-your-first-blog)
· [Get help](docs/troubleshooting.md)

## Install Blog Studio

Choose an available Blog Studio or suite bundle from
[Releases](https://github.com/dbbaskette/marketing-studio/releases), unzip it, and
run `bash install.sh` in the unpacked folder. No `.command` launcher is required.

Or install from source:

```sh
git clone https://github.com/dbbaskette/marketing-studio.git
cd marketing-studio
bash install.sh --studios blog
```

Choose assistant integration with `--target codex` or `--target claude`. Bring Git
and an installed, signed-in assistant. Prepared bundles include their selected
private runtimes and tools; source installers may fetch prerequisites. Existing
workspaces, settings and unrelated skills are preserved.

[Requirements and platform support](../../docs/installation.md) ·
[Independent bundles](../../docs/packaging.md)

## Start your first blog

1. **Open Blog Studio.** Use `marketing-studio open blog`, or launch it independently:

   ```sh
   sh ~/.local/share/blog-studio/studio
   ```

   Keep that terminal open while working. Complete shared setup once, then choose
   writing defaults and an optional brand in Settings.
2. **Choose your starting point.** **New blog** takes an idea, audience and point,
   or an outline and notes. Add sources on **Idea and sources**, then choose length,
   tone and an optional kind of post on **Writing preferences**. **Suggest three
   angles** uses the same sources. Supplied-source research and permission to search
   for additional sources are separate choices.
3. **Or choose Edit or polish a draft.** Paste writing, upload a file or read a
   Google Doc. Choose spelling and grammar suggestions, optional human-sounding
   wording or a voice guide, feedback, a reshape, or leave the draft unchanged.
   Research is not required just to copy edit.
4. **Read and refine.** The manuscript opens as a readable document. Go to a section
   or choose **Edit**; changes save as you type. A section note changes that section.
   Select words for Rephrase, Shorten, Expand, Fix or Ask. Whole-draft revision is a
   separate action. The Outline manages sections, and History compares and restores.
5. **Review changes, then send.** Suggestions are marked in the text with a reason
   and Accept/Reject. Accepting a suggestion preserves earlier text in History.
   Copy, download or choose a Google action yourself. Marking a blog as published
   records your decision; it does not publish to a website.

## Finish without losing your voice

**Polish** opens Review mode for marked copy edits. A voice guide and Humanize can
add wording suggestions, while facts, quotations, code and structure remain
protected. You can accept individual changes, edit them, reject them or use the
available batch actions; a suggestion that needs your judgment stays for review.

**Finishing** groups checks and proposals by purpose: Copy edit, Humanize, Quick
check, fact checking, headline/opening, feedback, voice, retrieval readiness (GEO)
and before-publishing tools. Quick check runs locally without an assistant.
Assistant-backed tools start only when requested; proposals wait for your decision.

**Voice guides** describe how writing should sound. Write one yourself or learn
one from samples, then apply it deliberately. Older author-profile tools remain
under Advanced. Sources used as writing examples supply style, not factual evidence.

[Full desk and tool guide](docs/runner.md) · [Voice walkthrough](docs/new-user-guide.md)

## Google Docs, sources and libraries

A Google Doc is read through your computer’s existing Google sign-in; it need not
be made public. Review the captured text before proceeding. Missing or unreadable
images are not evidence that their content was read.

Imported text stays local until you explicitly choose a Google update, suggestions
or comments. After a copy-edit review of an imported Doc, only accepted changes
are sent as suggestions. Reconcile accepted Google edits through the supported
workflow instead of overwriting a locally changed draft.

**Link to a published post** and **Get a GEO report for a published post** read the
page once, without running anything on it, and show what was read before anything
starts. A page built by scripts has no text of its own: **Ask Codex to find the
post’s text** (or Claude Code, as chosen under Settings) gives your assistant the
page’s head and excerpts of the scripts it loads from that site. It has no web
access and returns only where the page gets its text. Blog Studio reads that address
itself (https, the post’s own host, allowed by robots.txt) and uses it only when it
matches the page’s title, its description or the post’s own path. The address is remembered for that site on
this computer, so the next post there is read straight away.

The **team library** holds posts, examples and reusable material for a configured
team; without a Team Hub, that collection stays on this computer. The shared local
**Document Library** is separate: keep uploads for reuse across studios, or choose
**Only this blog**. A chosen library revision is copied into this blog. Taking a
newer revision is explicit and starts no research. Finished or published blogs can
be kept there as Markdown.

[Google Docs guide](docs/google-docs.md) ·
[Document Library](../../docs/shared-setup.md#the-document-library) ·
[Team workspaces](docs/team-workspace.md)

## Work in chat and return later

Start a new assistant conversation and ask it to use Blog Studio. In Codex you can
select `$blog-studio`; in Claude Code use `/blog-studio`. Ask for a complete blog,
an outline, proofreading or one specific edit. New chat work uses checked desk
records without starting another assistant process; expanding the request or
handing execution to the runner is explicit.

In the page, **Blogs → Continue editing** reopens saved work. In chat, ask for
**My blogs** or **Continue [title]**. The same saved blog and History are used in
both; ownership checks prevent a page worker and chat from editing over each other.

Older saved runs keep their compatible review flow. Eligible unfinished work can
move to the desk through a preview and explicit confirmation; missing-input or
unsupported work keeps its saved path. Migration grants no approval and starts no job.
Deleted blogs remain recoverable under **Recently deleted** for the stated retention period.

[Conversation desk](skills/blog-studio/references/conversation-desk.md) ·
[Saved-work compatibility](../../docs/saved-work-compatibility.md)

## Updates, help and development

Use **Status → Check this computer** for tools and assistant sign-in problems, or:

```sh
sh ~/.local/share/blog-studio/studio check
```

Failed steps explain retry and time-limit options while keeping saved work. Keep
private page links private. For an update, close idle studios and follow the
[installation guide](../../docs/installation.md); a source checkout can pull with
`git pull --ff-only` and reinstall its selected studio.

[Everyday requests](docs/prompt-cheat-sheet.md) · [Privacy](docs/privacy-review.md) ·
[Development](docs/development.md) · [What’s new](CHANGELOG.md)
