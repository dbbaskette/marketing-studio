![Blog Studio — Sources → Outline → Draft → Review → Team Library](docs/assets/blog-studio-header.png)

**Turn ideas, notes, and rough drafts into blogs that sound like you.**

Blog Studio works inside **Codex or Claude Code**. Tell it what you want to do:
plan an article, write a draft, improve something you already wrote, or talk through
an idea one question at a time. You stay in the same chat.

[**Get started**](#get-started) · [Simple commands](docs/prompt-cheat-sheet.md) · [First blog walkthrough](docs/new-user-guide.md)

## Get started

1. **[Download the installer](dist/blog-studio-installer.zip).** On GitHub, choose
   **Download raw file**. You need access to this private repository; your team
   administrator can also give you the installer.
2. **Expand the ZIP** and open **Install Blog Studio.command** in its `installer`
   folder. Choose Codex, Claude Code, or both, and follow the setup instructions.
3. **Open a new chat** in your chosen tool and say:
   **“Use Blog Studio. Help me start a blog.”**

Already installed? Download the latest installer and run it again, then open a
new chat. **Version 1.13.1** uses a normal local Git checkout for each Hub and keeps drafts, originals, review edits, selected sources, and
history together inside each blog folder. Reusable team knowledge has its own
readable memory library. Existing hubs upgrade during an authorized save or sync.

[Setup help, company laptop instructions, and updates →](docs/installation.md)

## Start with what you have

| You have… | Say… |
| --- | --- |
| A Google Doc | **Start from this Google Doc: [link].** |
| A draft on your computer | Attach it and say **Improve this draft.** |
| Notes or source material | **Use these notes to help me write a blog.** |
| An idea | **Make an outline about [topic].** |
| Experience you want to share | **Interview me.** |

Blog Studio asks for any missing details. You can ask for an outline, a first
draft, or feedback only. **“Help me set up my voice”** lets it learn from your
writing and preferences.

## Work with your team in Google Docs

If you start from a Google Doc, Blog Studio saves the original and a formatted
copy, then keeps **that same Doc** linked to your blog. Importing it does not
change the Google document or create a duplicate.

A typical review looks like this:

1. **“Start from this Google Doc: [link].”**
2. **“Proofread.”**
3. **“Push as suggestions.”**

Suggestions go back to the linked Doc so your team can review them. Blog Studio
checks the latest Google copy first. If suggested edits are unavailable, it uses
readable review comments and tells you where to find them. Say **“Show review
edits”**, then **“Apply edits 2 and 4”** to choose which comment proposals to apply.

After someone edits in Google, say **“Pull from Google Docs”** or **“Pull and
proofread.”** Blog Studio brings back the latest writing and saves a formatted
Word copy. It checks for competing edits before replacing local work.

Starting a blog in chat instead? **“Push to Google Docs”** sends it to Google.
Later pushes update the linked Doc. Use **“Push as suggestions”** when you want
review proposals instead of direct edits.

Google access needs a separate connection. You can say **“Use this folder for
team reviews: [link]”** and **“Use this as our blog template: [link].”** Blog Studio
remembers selected team preferences in your Hub and checks access before use.
These preferences do not change who can see a document.

Some document layouts need extra handling; Blog Studio will tell you when an
import or update cannot be completed.
[Google Docs setup and help →](docs/google-docs.md)

## Pick up where you left off

| Say… | To… |
| --- | --- |
| **My blogs.** | Find saved work |
| **Continue [title].** | Resume a blog |
| **Show status.** | See its working Doc link, save status, and next step |
| **Save and sync.** | Save your work and share it with your selected Team Hub |

A **Team Hub** is your team's private writing library on GitHub. It keeps blogs,
sources, notes, voices, and writing rules together, organized by author and title.
Earlier versions remain available.

Say **“Join our Hub: [repository link].”** Normal saves then share the selected
workspace with that Hub. Without one, your work stays on your computer. Blog
Studio tells you when a save is still waiting to be shared.

Your Hub lives at `~/blogs/<hub-name>/`, with readable shared files and Git history
together. Local drafts and sync state stay in the hidden `.blog-studio/` folder.
Existing Hubs can be moved by saying **“Move our Hub to the standard folder.”**

[Create or join a Team Hub →](docs/team-hub.md) · [More simple commands →](docs/prompt-cheat-sheet.md)

## See the team's work

Say **“Open editorial desk.”** A private page opens on your computer with:

- **Blogs in progress:** owners, due dates, stages, and working Google Doc links.
- **Needs attention:** review findings, waiting decisions, and stale companions.
- **Reference library:** uploaded material and earlier posts you can browse and curate.
- **Team memory:** shared notes, context, and writing rules.

Everyone with write access to your Hub uses the same controls. GitHub manages
membership. The desk runs locally; your private Hub also has readable editorial
and collection pages. Google links reflect saved information—ask in chat to
refresh Google content or feedback.

| Say… | To… |
| --- | --- |
| **Show our pipeline.** | See your team's writing stages and next actions |
| **What needs my attention?** | Find work needing a decision or review |
| **Import our old blogs from [folder or site].** | Preview a historical reference collection |
| **Find our previous blogs about [topic].** | Find relevant earlier writing |
| **Show evidence.** | Inspect support for important claims |
| **This needs a diagram.** | Prepare a visual companion |
| **Package this for launch.** | Prepare copy for your chosen channels |

Imports are previewed before a bulk save. Earlier posts remain references until
you explicitly choose to start an editable blog. Packages and visuals stay tied
to their draft; changes flag them for review. Preparing them does not publish.

The desk tells you whether work was **saved on your computer**, **shared with
your Hub**, or **waiting to sync**. Pending saves offer **Retry sync**. While a
view, search, or page loads, a message appears and page buttons pause.

If a reference changes while you edit its tags or notes, your proposed changes
stay in the form. Choose **Reload and compare**, then choose the latest saved
values or keep your proposal before saving again. Reloading alone does not save
changes.

Open a blog title or choose **Inspect finding** to see the saved writing and its
review status. **Copy request** gives you a short handoff to continue that specific
blog in chat. Editorial fields, reviews, and history open when you need them.

The desk shows your Hub access before editing. Read-only members can browse and
refresh; decisions and specialized memories explain how to continue in chat.

[Using the editorial desk →](docs/editorial-desk.md)

## The right help at the right time

**Idea → sources and voice → outline or draft → review → shared editing**

You can start at any step. Blog Studio opens only the instructions needed for your
request—a design called *progressive disclosure*. You do not need to manage the
individual skills yourself.

Writing guidance updates automatically for new blogs. Existing blogs keep their
saved guidance for consistency. New features sometimes need an installer update.

[How it works and token estimates →](docs/progressive-disclosure-roadmap.md)

## Your content stays under your control

Work stays in your chosen AI tool, on your computer, and in your selected private
Team Hub. Google transfers use the content and document you select. Blog Studio
adds no telemetry uploads. Your AI provider, GitHub, and Google process content
under your account settings.

[Privacy details](docs/privacy-review.md) · [House style](docs/house-style-guide.md) · [Troubleshooting](docs/troubleshooting.md)

---

**For developers and team administrators:** [Developer guide](docs/development.md) ·
[Roadmap](https://github.com/dbbaskette/blog-studio/issues/3) ·
[Performance evidence](docs/performance.md) · [Hub acceptance walkthrough](docs/hub-acceptance.md) · [Package details](PACKAGE.md)
