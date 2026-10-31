![Blog Studio — Sources → Outline → Draft → Review → Team Library](docs/assets/blog-studio-header.png)

# Blog Studio

**Turn ideas, notes, and rough drafts into blogs that sound like you.**

Blog Studio gives you a **browser UI to write and edit blogs**, powered by your
**Codex or Claude Code** assistant. Bring a topic, an outline or notes, or a draft;
the assistant writes, and you shape the result on one editing desk with notes,
selection edits and finishing tools. You can also work directly in chat.

[Install Blog Studio](#install-blog-studio) · [Start your first blog](#start-your-first-blog) · [Get help](docs/troubleshooting.md)

## Before you start

Use a Mac or Linux computer. The guided installer offers missing Python, Git,
Node.js and assistant CLIs, then installs Blog Studio and shared tools. Sign in
to your chosen assistant afterward.

GitHub and Google Docs are optional. You can start writing without setting up
team sharing or a document connection.

## Install Blog Studio

This source folder has `package.sh` to build an independent Blog Studio bundle
and `install.sh` to install Blog Studio. The Marketing Studio root has the same
filenames for the complete suite. See [package and install the studios](../../docs/packaging.md).

**[Download the Blog Studio installer](https://github.com/dbbaskette/marketing-studio/releases/latest/download/blog-studio-installer.zip)**
and unzip it. Open Terminal in `blog-studio-setup` and run `bash install.sh` on
macOS or Linux. No `.command` launcher is needed. This subset
installs Blog Studio and its own launcher; Marketing Studio is an optional home.

Or install from the consolidated source:

```sh
git clone https://github.com/dbbaskette/marketing-studio.git
cd marketing-studio
bash install.sh --studios blog
```

Use `--target codex` or `--target claude` for one assistant. Compatible existing
tools, workspaces, and settings are reused. The installer asks before installing
missing software. See the [guided installation reference](../../docs/installation.md)
for offline setup, updates, and rollback.

To write in chat, open your chosen tool in a folder for your writing and start a
**new chat**. Enter `$blog-studio` in Codex or `/blog-studio` in Claude Code.

## Start your first blog

### Drive the process from the browser UI

On a Mac, double-click **Open Blog Studio.command** in the **Applications**
folder inside your home folder. On Mac or Linux, open Terminal and run:

```sh
sh ~/.local/share/blog-studio/studio
```

The UI opens in your browser. Leave its terminal window open while it works;
press **Ctrl-C** there to stop. The launcher finds a supported Python for you,
even when the computer’s `python3` is older.

Once the page is open, use its controls to drive the work:

1. **Set your defaults.** On first launch, save your preferred assistant, author,
   tone and step time limit. You can change these later in **Settings**. Under **Brand
   skill**, enter its repository and release or choose an installed skill, just as in
   Training Studio. See [brand setup](docs/runner.md#your-brand-skill).
2. **Choose New blog.** New writing starts with two steps:
   - **Idea and sources.** Give the topic, audience and point, or bring an outline or
     notes. Add each source once: files (including PDF), pasted notes, Google Docs,
     web links or team library posts. The library choice also offers saved research,
     retaining its original purpose and rechecking it for the new blog. Preview captured text and choose each source's
     role: facts, attributed product messaging, or a writing example that supplies no
     factual evidence. Sources stay with this blog unless you choose to keep them in
     the team library. **Suggest three angles** uses this same inventory.
   - **Writing preferences.** Optionally choose a kind of post, length and tone.
     There is no second source picker. On the first step, **Research these sources
     before writing** requests supplied-source research; **Search for additional
     external sources** separately permits web or approved-site research. Leave both
     off to write directly from the material you supplied.

   To polish or review a draft, choose **Edit or polish a draft** on Home. It is one
   screen with no kind of post: your draft (pasted, uploaded or a Google Doc), then **What
   should happen first**: **Check spelling and grammar** (the default: each fix is marked
   in your text to accept or reject, and nothing changes until you accept; tick **Also
   suggest more human-sounding wording** to mix in Humanize's rewrites, at Light, Medium
   or Strong). **Use a voice guide** optionally adds wording suggestions from a saved
   voice to the same copy-edit pass. Choose the guide; facts, quotations and structure
   stay protected, and you accept or reject every change. **Just give
   feedback** (comments beside each part, nothing rewritten), **Reshape to fit a kind of
   post** (only this asks for a kind) or **Leave it as it is**. **Tone** and **Check facts
   against your sources** are optional folds. A draft's headings start its sections at
   whatever level it uses, such as the `###` headings of a Google Doc's export.

   **Check spelling and grammar** opens the blog in **Review mode**: the draft reads as a
   document, section by section, with each fix marked in place (struck words out,
   highlighted words in) and its reason, **Accept** and **Reject**. Each is labelled
   **Spelling**, **Grammar**, **Punctuation**, **Consistency**, **Wording** or, from
   Humanize, **Sounds human**; a wording fix may offer alternatives to pick from before **Accept**.
   Suggestions stay independent: accepting one changes another only where it touched that
   one's words, and never leaves one that would undo it. **Accept all** applies them in reading order and
   leaves a suggestion that changes a fact, code or shape for you to check. With
   human-sounding wording on, Quick check's findings are listed at the top with **Fix** and
   **Dismiss**. Click any paragraph to edit it yourself; **Check again** reruns the check. When nothing is left, a blog from a Google
   Doc sends only the accepted changes to the Doc as suggestions; others offer **Copy** and
   **Download**. **Open the full desk** has everything else.
3. **Press Start.** Nothing is needed from you after that. The page shows each step and
   opens the draft on the desk when it is ready.
4. **Read and edit.** The desk opens with the manuscript as a readable document.
   Use **Go to section** or **Edit** beside a heading to work on one section. Changes
   save as you type; changing views saves pending text first. **Full desk** keeps the
   all-sections editor available. Sections always show in the draft's own order. **Polish**
   opens Review mode, and **Back** there returns to where you were; the Finishing panel
   opens from the toolbar's **Finishing**. On a phone, **Go to section** and one **View and
   tools** fold sit above the text, so the title and the first paragraph show first.
   A note on a section rewrites that section; **Revise the whole draft** is a separate disclosure. Select text in an editor for **Rephrase**,
   **Shorten**, **Expand**, **Fix** or **Ask…**. **History** compares and restores earlier
   versions. The **Outline** tab manages sections and their briefs. **Sources** adds
   material without rewriting what you already have.
5. **Finish before publishing.** **Polish**, **Check claims**, **Tone and voice** and
   **Send and download** open contextual tools. **Finishing** groups the full tool list
   by purpose. Pending suggestions appear above the manuscript and remain optional:
   **Copy edit** (opens Review mode: grammar and wording fixes marked in your text to
   accept or reject), **Humanize** (light,
   medium or strong), **Quick check** (dashes, machine-sounding words and repetition, with
   no assistant), **Check facts against sources**, **Headline and opening**, **Feedback
   without a rewrite**, **Apply a voice** and
   **Before publishing** (the pre-publish check, **Repurpose**, and **Send to Google Doc**
   as suggestions). Each suggestion shows before and after. **Apply**, **Edit** or
   **Skip** it, or **Apply all**. Nothing changes until you apply, and the earlier text
   stays in History.
6. **Take it with you.** **Copy**, **Download**, **Google Doc** and **Mark as published**
   are in the desk's toolbar.

**Voice guides** in the sidebar says how a piece should sound: a name and a page of text.
Write one by hand, or make one from 3 to 20 samples, then use it with **Finishing → Apply
a voice**. The older voice tools (learning a voice from an author's posts, **Write as**
and a default voice) are hidden behind **Settings → Advanced**.

A Google Doc is read with this computer's Google sign-in, so it need not be shared.
**From the library** picks earlier posts and files from the **team library** as facts or
examples; **Add to library** takes files, links and Google Docs straight in.

Blogs started before the desk keep their step-by-step path: research, outline, draft,
review and handoff, stopping for your review where their review level says. Open one from
**Needs you** on Home, read the document and choose **Approve** or **Ask for changes**.
A finished one offers **Open on the desk** from its Done card or the manuscript editor.

If a step stops, the page says why and what to do: a CLI failure points at **Status →
Check this computer** and shows what the assistant printed; a step that ran out of time
says its limit, which lives in **Settings**, and offers **Try again with more time**.

You can leave the browser while it works and come back to **Home**. **Blogs** holds every
saved blog; each card has **Delete**, which asks for the blog's title and keeps the blog
for 30 days under **Recently deleted**. In **Status**, choose **Check this computer** for
assistant and sign-in checks, optional Team Hub tools, and what to do about anything
missing. You can also run `sh ~/.local/share/blog-studio/studio check` from Terminal.

[All UI controls, stages, and page/chat handoff →](docs/runner.md)

### Write in chat

You can also work directly with your assistant. Try:

> Use Blog Studio. Help me write a blog about [topic] for [audience].
> Ask for my notes, start with an outline, and wait for my approval.

Or attach a draft and say **“Improve this draft.”** For a smaller task, ask
**“Proofread”**, **“Suggest some titles”**, or **“Make an outline.”** To develop a
reusable writing style, say **“Help me set up my voice.”**

[Follow a first-session example →](docs/new-user-guide.md) · [Everyday commands →](docs/prompt-cheat-sheet.md)

## Save and come back

In the UI, open **Blogs** and choose **Continue editing** on your blog. It opens on the
desk where you left it; an older blog opens at its current stage. Your drafts, sources,
voice guides and earlier versions stay in your writing workspace on your computer.

In chat, say **“My blogs”** to find saved work or **“Continue [title]”** to resume.
**“Show status”** tells you where the current blog is saved and what to do next.

The page and chat use the same saved blog. You can move between them as you work.

A finished or published blog is also kept as Markdown in the Document Library that
every studio shares on this computer. It is local and separate from the team
library. To use a deck or an upload from it, choose **Library → From the Document
Library** under a blog's sources and give each document a role. The copy stays with
that blog only and is never shared with the team. When the library has a newer
revision of it, the desk says **Update available**; press **Use revision N** to take
it. Nothing changes until you do.

When you upload files, **Keep in library** (the default) also keeps a local copy of
each one in the Document Library for any studio; choose **Only this blog** to keep
none. Either way the file is shared with your team only as you chose for it. Blogs
and team library items kept before the Document Library existed can be added on
Marketing Studio's Library screen with **Add existing work to library**. See
[the Document Library](../../docs/shared-setup.md#the-document-library).

## Update or get help

For a cloned copy, run `git pull --ff-only` and then `bash install.sh --studios blog`
inside the `marketing-studio` folder. For a ZIP install, download the latest installer
ZIP and run setup again. Start a new chat afterwards. Updating keeps your
writing and saved voices. [More update options →](docs/installation.md#update)

If Blog Studio does not appear, first try a new chat. For installation checks,
repair, or other problems, use the [setup help](docs/troubleshooting.md).

## Explore when you need it

| You want to… | Read… |
| --- | --- |
| Learn from your writing and reuse your voice | [Voice setup walkthrough](docs/new-user-guide.md#build-and-reuse-your-voice) |
| Research a topic or check claims | [Writing and review commands](docs/prompt-cheat-sheet.md#write-and-review) |
| Edit and review with others in Google Docs | [Google Docs guide](docs/google-docs.md) |
| Share a repository with Training and Presentation Studio | [Join a team workspace](docs/team-workspace.md) |
| Use an existing Team Hub or move selected blogs | [Legacy Team Hubs](docs/team-hub.md) · [Migration](docs/team-workspace.md#bring-selected-work-from-a-legacy-team-hub) |
| Browse the editorial pipeline, the team library or import earlier posts | [Library and team tools](docs/editorial-desk.md) |
| Understand where your content goes | [Privacy details](docs/privacy-review.md) |

[What's new](CHANGELOG.md) · [Developer guide](docs/development.md)

Saved older work and its retained paths are described in [saved work compatibility](../../docs/saved-work-compatibility.md).
