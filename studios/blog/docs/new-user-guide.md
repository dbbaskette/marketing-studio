# Blog Studio: your first writing session

Blog Studio is a skill inside the Codex or Claude Code CLI. You talk to it in plain language: bring an idea, notes, an outline, or an existing blog, then choose how much help you want. The browser preview is an optional prompt generator; your writing session happens in the CLI.

Follow this walkthrough to create, revise, and resume your first blog. The example
uses fictional notes so you can try the process before using your own material.
For shorter copy-and-paste requests, see the [prompt cheat sheet](prompt-cheat-sheet.md).

## 1. Open your writing workspace

Install Blog Studio using the [setup guide](installation.md), then sign in to your
chosen writing tool, Codex or Claude Code. Use a folder for your writing, separate
from the skill installation.

On macOS or Linux, open a terminal and create your writing folder:

```sh
mkdir -p "$HOME/Documents/Blog-Studio"
cd "$HOME/Documents/Blog-Studio"
```

Launch **one** of your installed writing tools in that folder:

```sh
codex
```

Or, for Claude Code:

```sh
claude
```

If the command is unavailable, follow the [setup guide](installation.md) to check
your installation. You only need one writing tool to follow this walkthrough.

Once the CLI chat is open, enter `$blog-studio` in Codex or `/blog-studio` in Claude Code. Then send the following prompts as chat messages. **The shell commands above go in Terminal; the writing prompts below go inside the CLI chat.**

## 2. Choose how to start

Send:

> I want to use Blog Studio to work on a blog. Show me my starting choices and ask whether I have source material. Do not start writing yet.

Look for six choices: improve an existing draft, write a first draft, make an outline, write from an outline, interview you, or help discover an idea. It should offer ways to provide sources and choose a voice. A saved voice profile is optional.

For a specific request, Blog Studio should follow your instructions directly instead of making you repeat them through menus.

## 3. Make an outline from notes

Send:

> Use Blog Studio to make an outline only. Working title: “A clearer handoff starts with a named owner.” Audience: team leads. Takeaway: a handoff note should name who takes the next step. Use a direct, warm tone. Use only the fictional notes below; do not research outside sources. Aim for a future article of about 600 words. Save the outline and tell me its article ID and file location. Stop before drafting.
>
> Notes: In a fictional Tuesday exercise, we reviewed six handoff notes. Two did not identify who should act next. We did not measure delays, costs, productivity, or business outcomes. Our proposed experiment is to add an “Owner / Next action / Check-in date” line to each note for one week. We do not yet have results.

**What to expect:** You get an outline, not a full article. It distinguishes observations from the proposed experiment. It invents no productivity gain, customer story, quotation, or completed result. It names where the outline was saved.

## 4. Turn that outline into a first draft

Send in the same chat:

> Turn the saved outline into a first draft of about 600 words. Keep the same notes and tone. Make clear that the exercise is fictional. Use a practical example of the proposed handoff line, labeled as an example. Do not invent outcomes. Save the draft and stop there.

**What to expect:** It reuses the brief and sources, writes the draft, and reports the save location. It should not ask you to re-upload the notes or require another outline approval.

## 5. Revise without losing the earlier draft

Send:

> Tighten the introduction and remove repetition. Keep the facts, stance, and practical example intact. Save a new revision and retain the previous draft. Briefly explain the edits. Do not run additional reviews yet.

Then:

> Check the factual claims against my original notes. Give feedback only; do not rewrite. Identify anything unsupported, and say what material you checked.

**What to expect:** The earlier draft remains available. The review cites the supplied notes and flags unsupported claims. Feedback alone should not change the manuscript.

## 6. Leave and come back

Before closing the CLI, send:

> Save our current work. Tell me the article ID, workspace location, and what we should do next.

Quit the CLI normally. Open it again using the commands in step 1, in the **same writing folder**. Invoke Blog Studio and send:

> Resume my saved article “A clearer handoff starts with a named owner.” Show me its current stage, saved draft, and next step. Do not start a new article or update its voice or writing guidance.

Use the saved article ID if there are several matches.

**What to expect:** It finds the existing article, retains its original material and revisions, and resumes without repeating the intake. An ongoing article should keep its saved voice and guidance versions. New writing tasks check for newer guidance automatically; executable updates still require the installer.

## Try the other starting paths

To start a different article, open a new chat in your writing folder. Invoke Blog Studio, then choose one of these prompts.

| What you want | Prompt to try | Expected stopping point |
| --- | --- | --- |
| Find an idea | “Help me discover a blog idea for new team leads about everyday collaboration. Give me three topic options and their reader takeaway. Do not research or draft.” | Topic options |
| Be interviewed | “Interview me about a work habit I have changed. Ask one focused question at a time. Help me reach an outline, then stop.” | One question per turn; eventually an outline |
| Write a first draft | “Write a first draft using the fictional handoff notes from this guide. I will paste them next. Wait for my notes. Use a plain, warm tone and stop at the draft.” | Wait for notes, then a draft |
| Use your outline | “Write a short draft from this outline: 1. Why an unnamed owner leaves the next step unclear; 2. A proposed Owner / Next action / Check-in date line; 3. A one-week experiment. Treat this as a proposal with no measured results. No outside research.” | A draft following your structure |
| Improve your draft | “I will paste an existing blog next. Wait for it, then give structural feedback only. Preserve my original and do not rewrite yet.” | Wait, then feedback |

For the first-draft example, paste the actual notes from step 3. A new chat should not be expected to know the contents of this guide unless you supply them or its local file path.

## Build and reuse your voice

Start with writing you actually authored. Send:

> Help me create a reusable voice profile named “My blog voice.” This is a voice-only task; do not create an article. Ask for my author background and representative writing samples. Show me a short voice summary and an audition before treating it as confirmed.

You can provide authored blog links, pasted passages, local sample files, and a LinkedIn profile or About text. Identify which samples best represent how you want to sound. LinkedIn background helps with identity and expertise; authored writing helps with prose style. If a link cannot be read, supply the relevant text or a file.

Correct the audition, then explicitly ask to confirm and save the profile. In a later article, say:

> Use my saved “My blog voice” profile for this new article.

**What to expect:** It separates observed style from preferences and biography. It does not invent your experiences. Changing the profile later should not silently change the voice attached to an existing article.

## Use your own files and links

In a CLI, a local path or pasted text is the simplest input. Describe the file's role:

> Use the file at `/absolute/path/to/my-notes.md` as factual source material for a new outline. Read that file, preserve the original, and tell me if anything is inaccessible.

For an existing draft, say it is the manuscript to edit. For your own writing, say it is a voice sample. For someone else's blog, say whether it is evidence or inspiration.

Use the full path to a file accessible from your writing session. PDF and Word extraction depends on the tools available in that CLI. An unreadable file or link should produce a clear limitation, not a claim that it was read.

## Where your work goes

The default author workspace is `.blog-studio` inside the folder where you launched the CLI. In this walkthrough, that is `Documents/Blog-Studio/.blog-studio`. Ask Blog Studio to show the exact saved file when you want to inspect it.

Keep your writing out of the skill installation directory. To share work, create or join a private [Team Hub](team-hub.md). Once selected, normal saves synchronize changed items and their selected dependencies; offline saves queue until they can sync. Without a Hub, your work stays local. [Google Docs](google-docs.md) requires its own connection and a request to send or bring back edits.

## Review together in Google Docs

Connect Google using the [Google Docs guide](google-docs.md). To create your shared
editing copy, say **“Push to Google Docs.”** Blog Studio remembers its link.

For proofreading changes your team should approve:

1. Say **“Proofread.”** Review the proposed changes.
2. Say **“Push as suggestions.”** Blog Studio checks the latest Google copy,
   brings back changes, and refreshes affected findings before submitting. If
   both copies changed, it preserves your work and helps resolve the differences.
3. Review the pending suggestions and comments in Google Docs.
4. Say **“Pull from Google Docs.”** Accepted wording returns to your draft.
   Pending suggestions stay separate; the formatted DOCX snapshot is retained.

You do not need a separate pull before sending suggestions. If someone edits the
Doc during submission, Blog Studio stops and refreshes the review. Ordinary
**“Push to Google Docs”** applies updates directly; **“Push as suggestions”** leaves
proposals for the team to accept or reject.

This feature needs the **1.9 installer update** once. Download the current trusted
bundle, run Install for the same writing tools, and start a new session. The
writing-instruction refresh does not install new executable helpers.

## If something fails

If the skill is missing, first start a new CLI session. If Blog Studio is available,
ask:

> Check my Blog Studio setup and tell me how to fix anything missing.

If it is still unavailable, open a terminal in the expanded installer bundle and run:

```sh
sh installer/install.sh check
```

See the [setup guide](installation.md) for installation and repair steps.
If you need help, include which writing tool you used, what you asked it to do,
the response or error, and the article ID and saved location if available.
Avoid including credentials or private source content.

## See where your blog stands

Say **“Show status”** in chat, or **“Continue [title]”** to select a blog. The
[status card](status-card.md) shows stage, Google and Hub links, save status,
and the next useful action. Runtime 1.7.0 adds this card, defaults, change summaries,
and guarded undo; use the updated installer and start a new session.

## Everyday requests

In the CLI conversation, try these plain-language requests:

1. “Check my Blog Studio setup.” Expect a short readiness report. Missing optional
   Google connectivity should not prevent local writing.
2. “Show my blogs.” Expect article names, stages, last activity, and next steps for
   the current workspace; an empty workspace should offer a new start.
3. “Continue A clearer handoff starts with a named owner.” Expect the saved article and exact pins, without
   repeating intake. Duplicate names should prompt a choice.
4. “What do you know about this article?” Expect selected sources/roles, voice,
   active article preferences, team context, and review state.
5. “Remember for this article: use descriptive headings.” Then “Correct that:
   use question headings.” Then “Forget that heading preference.” Expect the
   active preference to change while the draft and old history remain intact.
6. “Stop using that team rule in this article.” Expect only this article's
   selection to change; other users retain their selections.

Use the latest trusted installer for executable updates, then start a new session.
Writing guidance updates automatically for new tasks; saved articles retain their
selected guidance. For a shared preference, explicitly say “for our team” and
select a Team Hub.

## Browse shared blogs in GitHub

After saving or syncing to a selected Team Hub, open its repository homepage. Follow an article title into `blogs/<author>/<title>/README.md`. Try the
outline, context, and history links. An article without a chosen author or voice
appears under Unassigned; ask Blog Studio to set its author when appropriate.

Ask Blog Studio to rename an article or change its author and sync. Its readable
folder should move, while the canonical history stays intact. Use Blog Studio for
edits: the generated GitHub pages are browsing views. For a review-required hub,
merge the authorized contribution before expecting new views on main.

For a linked blog, its page includes **Open working Google Doc** and the last
capture time. That timestamp describes the saved snapshot; ask Blog Studio to
check the linked Doc for a current comparison.

## Faster repeat work

Runtime 1.8 resumes with a compact status and opens the relevant passages as needed.
Identical mechanical checks can be reused; this never substitutes for reading and
editorial judgment. You can say **“Show the sources for this section”** or
**“Clear local caches.”** Clearing these caches keeps your drafts and history.
Reopen the trusted installer once to get the new helpers.
