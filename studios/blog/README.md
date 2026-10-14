![Blog Studio — Sources → Outline → Draft → Review → Team Library](docs/assets/blog-studio-header.png)

# Blog Studio

**Turn ideas, notes, and rough drafts into blogs that sound like you.**

Blog Studio is a writing assistant for **Codex or Claude Code**. Bring an idea,
source material, or an existing draft. Choose your audience and voice, then work
in chat or use a guided browser page that stops for your approval at each stage.

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
Then open your chosen tool in a folder for your writing and start a **new chat**.
Enter `$blog-studio` in Codex or `/blog-studio` in Claude Code to load the skill.

[Detailed setup, company laptop help, and repair instructions →](docs/installation.md)

## Start your first blog

### Use the writing page

In your Codex or Claude Code chat, say:

> Use Blog Studio. Open the page.

On the page, choose **New blog**. The three-step wizard asks about your topic
and audience, how you want to work, and the sources and assistant to use.
Choose **Write a blog**, **Outline only**, **Revise a draft**, or **Review a draft**.
You can upload notes or a manuscript and choose a tone or saved author voice.

Your assistant works through the selected stages. Read each result, then
**Approve** it or **Ask for changes**. **Home** shows what needs your attention;
**Blogs** holds your saved work.

Keep the terminal that opened the page running. You can close the browser and
return while the assistant works.

[Writing page walkthrough and controls →](docs/runner.md)

### Write in chat

You can also work directly with your assistant. Try:

> Use Blog Studio. Help me write a blog about [topic] for [audience].
> Ask for my notes, start with an outline, and wait for my approval.

Or attach a draft and say **“Improve this draft.”** For a smaller task, ask
**“Proofread”**, **“Suggest some titles”**, or **“Make an outline.”** To develop a
reusable writing style, say **“Help me set up my voice.”**

[Follow a first-session example →](docs/new-user-guide.md) · [Everyday commands →](docs/prompt-cheat-sheet.md)

## Save and come back

Your drafts, sources, voice profiles, and earlier revisions stay in your writing
workspace on your computer. In chat, say **“My blogs”** to find saved work or
**“Continue [title]”** to resume. **“Show status”** tells you where the current
blog is saved and what to do next.

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
| Share blogs, sources, and writing rules with a team | [Create or join a private Team Hub](docs/team-hub.md) |
| Browse the editorial pipeline or import earlier posts | [Editorial tools and reference library](docs/editorial-desk.md) |
| Understand where your content goes | [Privacy details](docs/privacy-review.md) |

[What's new](CHANGELOG.md) · [Developer guide](docs/development.md)
