![Blog Studio — Sources → Outline → Draft → Review → Team Library](docs/assets/blog-studio-header.png)

**Turn ideas, notes, and rough drafts into blogs that sound like you.**

Blog Studio works inside **Codex or Claude Code**, the AI chat tools you already use.
Start with a conversation. Bring your notes, ask for an outline, improve a draft,
or let Blog Studio interview you one question at a time.

[**Get started**](#get-started) · [Simple commands](docs/prompt-cheat-sheet.md) · [First blog walkthrough](docs/new-user-guide.md)

## Get started

1. **Install Blog Studio.** [Download the installer](dist/blog-studio-installer.zip),
   expand it, and open **Install Blog Studio.command** in the `installer` folder.
   Choose Codex, Claude Code, or both. You need access to this private repository.
2. **Open a new chat** in your chosen tool after setup finishes.
3. **Say:** “Use Blog Studio. Help me start a blog.”

Setup checks the tools and sign-ins you need and explains anything missing.
Already have a draft? Attach it and say **“Improve this draft.”**

Company laptop or prefer a shell script? Keep the expanded bundle together and
run `sh installer/install.sh` from its top folder in your approved terminal.
[Setup, updates, and troubleshooting →](docs/installation.md)

## Just ask

| Say | Blog Studio helps you… |
| --- | --- |
| **Interview me.** | Turn your experience into an idea worth writing about |
| **Use these notes.** | Bring sources into the current blog |
| **Help me set up my voice.** | Learn from your writing and preferences |
| **Make an outline.** | Plan the article before drafting |
| **Write the draft.** | Build on your topic, notes, and outline |
| **Proofread.** | Fix spelling, grammar, and punctuation |
| **Continue [title].** | Pick up saved work and see the next step |
| **Show status.** | See the blog’s links and save status |

You can also start from a blank page, supply an outline, or request feedback only.
Blog Studio asks for the missing details; you do not need a long prompt.
[More simple commands →](docs/prompt-cheat-sheet.md)

## Write here. Review together in Google Docs.

Say **“Push to Google Docs.”** After your team edits the document, say
**“Pull from Google Docs.”** Or combine it with **“Pull and proofread.”**
To let the team approve proofreading changes, say **“Push as suggestions.”**
Blog Studio checks the latest Google copy before submitting.

A supported pull keeps a formatted **Word/DOCX snapshot** alongside readable
Markdown. Blog Studio checks for competing edits and preserves formatting during
supported wording updates. Your working Google Doc link stays with the blog.
Google access needs a separate connection; setup will identify what is available.
[Connect Google Docs →](docs/google-docs.md)

## Keep your team’s work together

A **Team Hub** is your team’s private writing library on GitHub. It holds blogs,
sources, notes, voices, and shared writing rules, with readable author and title
folders and earlier versions you can revisit.

Ask **“Join our Hub: [repository link].”** Normal saves then synchronize the selected
workspace. Without a Hub, your work stays local. Offline or review-required saves
show as waiting until they are actually shared.
[Create or join a Team Hub →](docs/team-hub.md)

## The right help at the right time

Blog Studio loads guidance as you need it:

**Your idea → sources and voice → outline or draft → requested checks → handoff**

This is called *progressive disclosure*. You stay in chat while the skill opens
only the relevant writing instructions. On resume, it starts with a compact
summary and reads the passages or full documents needed for your next request.
Unchanged mechanical checks can be reused; new edits still trigger fresh checks.

Routine writing guidance updates arrive automatically for new tasks. Existing
blogs retain their saved guidance so an update does not change a draft’s rules
midway through. New helper features, including runtime **1.8**, need a one-time
update through the installer.

[How it works and token estimates →](docs/progressive-disclosure-roadmap.md)

## Your content stays under your control

Work stays in your chosen AI tool, local workspace, and selected private Team Hub.
Google transfers send the selected content to the chosen document. Blog Studio
adds no telemetry uploads. Your AI provider, GitHub, and Google still process
content under your account settings.

[Privacy details](docs/privacy-review.md) · [House style](docs/house-style-guide.md) ·
[Status card](docs/status-card.md) · [Troubleshooting](docs/troubleshooting.md)

---

**Building or administering Blog Studio?** See the [developer guide](docs/development.md),
[performance evidence](docs/performance.md), [roadmap](https://github.com/dbbaskette/blog-studio/issues/3),
and [package details](PACKAGE.md). Live account and team pilots are tracked separately.
