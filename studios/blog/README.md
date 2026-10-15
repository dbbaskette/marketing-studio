![Blog Studio — Sources → Outline → Draft → Review → Team Library](docs/assets/blog-studio-header.png)

# Blog Studio

**Turn ideas, notes, and rough drafts into blogs that sound like you.**

Blog Studio gives you a **browser UI to create, run, and review blogs**, powered
by your **Codex or Claude Code** assistant. Bring an idea, notes, or a draft; the
assistant does the writing and the UI brings each stage back for your approval.
You can also work directly in chat.

[Install Blog Studio](#install-blog-studio) · [Start your first blog](#start-your-first-blog) · [Get help](docs/troubleshooting.md)

## Before you start

You need:

- **A Mac or Linux computer.**
- **Codex or Claude Code**, installed on that computer and signed in. You only need one.
- **Python 3.11 or later.** If you need help installing Python, see the
  [setup guide](docs/installation.md#before-you-start).

GitHub and Google Docs are optional. You can start writing without setting up
team sharing or a document connection.

## Install Blog Studio

Choose either method. Both run the same setup.

### Clone and run

If you have Git, open Terminal and run:

```sh
git clone https://github.com/dbbaskette/blog-studio.git
cd blog-studio
sh installer/install.sh
```

This installs the current code from the repository. To install a packaged
release instead, use the ZIP below.

### Download the ZIP

1. **[Download the installer ZIP](https://github.com/dbbaskette/blog-studio/releases/latest/download/blog-studio-installer.zip).**
   Choose `blog-studio-installer.zip` if you are browsing the
   [release page](https://github.com/dbbaskette/blog-studio/releases/latest).
2. **Expand the ZIP.** Keep the resulting `blog-studio-setup` folder together.
3. **Run setup.** On macOS, double-click `Install Blog Studio.command` inside its
   `installer` folder. On Linux, or if the Mac launcher will not open, open
   Terminal and run the following if you extracted the ZIP into Downloads:

   ```sh
   cd ~/Downloads/blog-studio-setup
   sh installer/install.sh
   ```

   If you extracted it somewhere else, use that folder's path in the first line.

### Finish setup

Choose **Codex**, **Claude Code**, or **Both** and follow the setup prompts.
Setup prints how to open Blog Studio and checks this computer, with the next
steps for anything missing. You can then use the UI below.

To write in chat, open your chosen tool in a folder for your writing and start a
**new chat**. Enter `$blog-studio` in Codex or `/blog-studio` in Claude Code.

[Detailed setup, company laptop help, and repair instructions →](docs/installation.md)

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
   **Settings**.
2. **Choose New blog.** Work through three short steps: give the topic and
   audience; choose **Write a blog**, **Outline only**, **Revise a draft**, or
   **Review a draft** and a voice; then select or upload sources, choose Codex or
   Claude Code, and set limits. To revise or review, supply the manuscript.
3. **Press Start the blog.** Blog Studio starts the selected assistant and runs
   the next stage. The progress view shows its steps and the files made so far.
   A new blog can go through research, outline, draft, review, and export package.
4. **Review when it needs you.** Open the item under **Needs you** on Home or
   choose **Review** on its run. Read the document, assistant notes, and any
   comparison with the last approved version. Choose **Approve** and confirm to
   let the next stage begin.
5. **Request changes in the UI.** Choose **Ask for changes**, select the stage,
   and describe what you want—for example, “Make the introduction more direct.”
   The next version comes back for review. If the run is paused, choose **Resume**.
6. **Collect your writing.** Open saved documents under **Made so far** and use
   **Download** to keep a Markdown copy. Your originals, stages, and decisions
   stay saved with the blog.

You can leave the browser while it works and return to **Home** to see **Needs
you**, **In progress**, and **Finished**. Use **Pause after this step** to pause
between stages, or **Stop** to end a running step. **Blogs** holds your saved
runs. In **Status**, choose **Check this computer** for assistant and sign-in
checks, optional Team Hub tools, and instructions for anything missing. You can
also run `sh ~/.local/share/blog-studio/studio check` from Terminal.

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

For a cloned copy, run `git pull --ff-only` and then `sh installer/install.sh`
inside the `blog-studio` folder. For a ZIP install, download the latest installer
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
| Browse the editorial pipeline or import earlier posts | [Editorial tools and reference library](docs/editorial-desk.md) |
| Understand where your content goes | [Privacy details](docs/privacy-review.md) |

[What's new](CHANGELOG.md) · [Developer guide](docs/development.md)
