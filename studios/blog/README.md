![Blog Studio — Sources → Outline → Draft → Review → Team Library](docs/assets/blog-studio-header.png)

# Blog Studio

**Turn ideas, notes, and rough drafts into blogs that sound like you.**

Blog Studio gives you a **browser UI to create, run, and review blogs**, powered
by your **Codex or Claude Code** assistant. Bring an idea, notes, or a draft; the
assistant does the writing and the UI brings each stage back for your approval.
You can also work directly in chat.

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
   tone, research choice, and step time limit. You can change these later in
   **Settings**. Under **Brand skill**, enter its repository and release or choose
   an installed skill, just as in Training Studio. See [brand setup](docs/runner.md#your-brand-skill).
2. **Choose New blog.** Choose **Write a blog**, **Outline only**, **Revise a draft**,
   or **Review a draft**; give the topic and audience, then **Write as** (whose
   voice) and **Kind of post** (the shape of the piece); then upload files or select
   saved references, and set the tone, author and an optional brand. To revise or review, supply the manuscript.
   To start from your own documents, choose **New blog from my files** on Home: upload
   them or paste Google Doc links and say what each is for, facts that may be quoted or
   an example of the kind of post you want (its shape, never its facts); then pick one
   of three suggested angles, or give the title, the point and the reader yourself, and
   the usual outline and draft follow. **Write as** chooses the voice there too: your
   default voice, a saved profile, or no particular voice with a tone.
   A Doc is read with this computer's Google sign-in, so it does not need to be shared.
   The files land in the **team library** unless you untick **Keep**; then they stay
   on this computer, though the blog's outline and draft may quote them and are
   shared like any other blog. Every finished blog lands in the library too, and
   **From the library** picks finished blogs, files and links as facts or examples
   for the next one, with no re-adding; **Add to library** takes files, links and
   Google Docs straight in, by one author or each post's own.
   For a blog already in Google Docs, choose **Open Google Doc** on Home or Blogs,
   preview its link and confirm the manuscript before importing. The same Doc
   stays linked; importing does not start an assistant or change Google.
3. **Press Start the blog.** Blog Studio starts the selected assistant and runs
   the next stage. The progress view shows its steps and the files made so far.
   A new blog can go through research, outline, draft, review, and export package.
4. **Review when it needs you.** With the default **Balanced** review level,
   Blog Studio stops for you at the outline, with its research beside it (at the
   draft, for a blog that starts from your outline), and
   at the last step, with the steps since then beside it. Other steps
   carry on by themselves. **Step by step** stops at every stage. Open the item
   under **Needs you** on Home or choose **Review** on its run. Read the
   document, assistant notes, and any comparison with the last approved version.
   Choose **Approve** and confirm to let the run continue. **Finish**, at the last
   step, always asks first and keeps the draft in the team library.
5. **Request changes in the UI.** Choose **Ask for changes**, select the stage,
   and describe what you want—for example, “Make the introduction more direct.”
   The next version comes back for review. If the run is paused, choose **Resume**.
6. **Collect your writing.** Open saved documents under **Made so far** and use
   **Download** to keep a Markdown copy. Your originals, stages, and decisions
   stay saved with the blog.

If a step stops, its run says why and what to do: a CLI failure points at
**Status → Check this computer** and shows what the assistant printed; a step that
ran out of time says its limit, which lives in **Settings**, beside **Try again
with more time**. Research the independent check refused is kept on this computer
and listed by what the check objected to; **Try again** continues from it, and
**Continue without research** carries on without it.

You can leave the browser while it works and return to **Home** to see **Needs
you**, **In progress**, and **Finished**. Use **Pause after this step** to pause
between stages, or **Stop** to end a running step. **Blogs** holds your saved
runs; each card has **Delete**, which asks for the blog's title and keeps the
blog for 30 days under **Recently deleted**. In **Status**, choose **Check this
computer** for assistant and sign-in checks, optional Team Hub tools, and
instructions for anything missing. You can also run
`sh ~/.local/share/blog-studio/studio check` from Terminal.

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

In the UI, open **Blogs**, select your blog, and review its current stage or
choose **Resume** if it is paused. Your drafts, sources, voice profiles, and
earlier revisions stay in your writing workspace on your computer.

In chat, say **“My blogs”** to find saved work or **“Continue [title]”** to resume.
**“Show status”** tells you where the current blog is saved and what to do next.

The page and chat use the same saved blog. You can move between them as you work.

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
| Browse the editorial pipeline, the team library or import earlier posts | [Editorial tools and reference library](docs/editorial-desk.md) |
| Understand where your content goes | [Privacy details](docs/privacy-review.md) |

[What's new](CHANGELOG.md) · [Developer guide](docs/development.md)
