# Blog Studio: your first writing session

Blog Studio is a skill inside the Codex or Claude Code CLI. You talk to it in plain language: bring an idea, notes, an outline, or an existing blog, then choose how much help you want. The browser preview is an optional prompt generator; your writing session happens in the CLI.

This guide gives you a small, repeatable test. The examples use fictional material. The expected results below are things to check, not claims that the live tests have already passed.

## 1. Open your writing workspace

For the fresh Tart test Mac, GitHub, Codex, and Claude are signed in and Blog Studio is installed for both. Use the VM named **blog-studio-login-fresh-20261002**. Open **Terminal inside that VM** using Finder → Go → Utilities → Terminal.

Run these commands to test Codex:

```sh
mkdir -p "$HOME/Documents/Blog-Studio-Test/codex"
cd "$HOME/Documents/Blog-Studio-Test/codex"
/opt/homebrew/bin/codex
```

Or run these to test Claude Code:

```sh
mkdir -p "$HOME/Documents/Blog-Studio-Test/claude"
cd "$HOME/Documents/Blog-Studio-Test/claude"
/opt/homebrew/bin/claude
```

These are separate test folders so the two CLIs start with independent articles and voices. Run the same walkthrough in each. On another computer, install Blog Studio first using the [setup guide](installation.md); the executable locations may differ.

Once the CLI chat is open, enter `$blog-studio` in Codex or `/blog-studio` in Claude Code. Then send the following prompts as chat messages. **The shell commands above go in Terminal; the writing prompts below go inside the CLI chat.**

## 2. Check the welcome flow

Send:

> I want to use Blog Studio to work on a blog. Show me my starting choices and ask whether I have source material. Do not start writing yet.

Look for six choices: improve an existing draft, write a first draft, make an outline, write from an outline, interview you, or help discover an idea. It should offer ways to provide sources and choose a voice. A saved voice profile is optional.

For a specific request, Blog Studio should follow your instructions directly instead of making you repeat them through menus.

## 3. Make an outline from notes

Send:

> Use Blog Studio to make an outline only. Working title: “A clearer handoff starts with a named owner.” Audience: team leads. Takeaway: a handoff note should name who takes the next step. Use a direct, warm tone. Use only the fictional notes below; do not research outside sources. Aim for a future article of about 600 words. Save the outline and tell me its article ID and file location. Stop before drafting.
>
> Notes: In a fictional Tuesday exercise, we reviewed six handoff notes. Two did not identify who should act next. We did not measure delays, costs, productivity, or business outcomes. Our proposed experiment is to add an “Owner / Next action / Check-in date” line to each note for one week. We do not yet have results.

**Check:** You get an outline, not a full article. It distinguishes observations from the proposed experiment. It invents no productivity gain, customer story, quotation, or completed result. It names where the outline was saved.

## 4. Turn that outline into a first draft

Send in the same chat:

> Turn the saved outline into a first draft of about 600 words. Keep the same notes and tone. Make clear that the exercise is fictional. Use a practical example of the proposed handoff line, labeled as an example. Do not invent outcomes. Save the draft and stop there.

**Check:** It reuses the brief and sources, writes the draft, and reports the save location. It should not ask you to re-upload the notes or require another outline approval.

## 5. Revise without losing the earlier draft

Send:

> Tighten the introduction and remove repetition. Keep the facts, stance, and practical example intact. Save a new revision and retain the previous draft. Briefly explain the edits. Do not run additional reviews yet.

Then:

> Check the factual claims against my original notes. Give feedback only; do not rewrite. Identify anything unsupported, and say what material you checked.

**Check:** The earlier draft remains available. The review cites the supplied notes and flags unsupported claims. Feedback alone should not change the manuscript.

## 6. Leave and come back

Before closing the CLI, send:

> Save our current work. Tell me the article ID, workspace location, and what we should do next.

Quit the CLI normally. Open it again using the commands in step 1, in the **same test folder**. Invoke Blog Studio and send:

> Resume my saved article “A clearer handoff starts with a named owner.” Show me its current stage, saved draft, and next step. Do not start a new article or update its voice or writing guidance.

Use the saved article ID if there are several matches.

**Check:** It finds the existing article, retains its original material and revisions, and resumes without repeating the intake. An ongoing article should keep its saved voice and guidance versions. New writing tasks check for newer guidance automatically; executable updates still require the installer.

## Try the other starting paths

Start a new chat in your chosen test folder for each independent test. Invoke Blog Studio, then use one of these prompts.

| What you want | Prompt to try | Expected stopping point |
| --- | --- | --- |
| Find an idea | “Help me discover a blog idea for new team leads about everyday collaboration. Give me three topic options and their reader takeaway. Do not research or draft.” | Topic options |
| Be interviewed | “Interview me about a work habit I have changed. Ask one focused question at a time. Help me reach an outline, then stop.” | One question per turn; eventually an outline |
| Write a first draft | “Write a first draft using the fictional handoff notes from this guide. I will paste them next. Wait for my notes. Use a plain, warm tone and stop at the draft.” | Wait for notes, then a draft |
| Use your outline | “Write a short draft from this outline: 1. Why an unnamed owner leaves the next step unclear; 2. A proposed Owner / Next action / Check-in date line; 3. A one-week experiment. Treat this as a proposal with no measured results. No outside research.” | A draft following your structure |
| Improve your draft | “I will paste an existing blog next. Wait for it, then give structural feedback only. Preserve my original and do not rewrite yet.” | Wait, then feedback |

For the first-draft test, paste the actual notes from step 3. A new chat should not be expected to know the contents of this guide unless you supply them or its local file path.

## Build and reuse your voice

Start with writing you actually authored. Send:

> Help me create a reusable voice profile named “My blog voice.” This is a voice-only task; do not create an article. Ask for my author background and representative writing samples. Show me a short voice summary and an audition before treating it as confirmed.

You can provide authored blog links, pasted passages, local sample files, and a LinkedIn profile or About text. Identify which samples best represent how you want to sound. LinkedIn background helps with identity and expertise; authored writing helps with prose style. If a link cannot be read, supply the relevant text or a file.

Correct the audition, then explicitly ask to confirm and save the profile. In a later article, say:

> Use my saved “My blog voice” profile for this new article.

**Check:** It separates observed style from preferences and biography. It does not invent your experiences. Changing the profile later should not silently change the voice attached to an existing article.

## Use your own files and links

In a CLI, a local path or pasted text is the simplest input. Describe the file's role:

> Use the file at `/absolute/path/to/my-notes.md` as factual source material for a new outline. Read that file, preserve the original, and tell me if anything is inaccessible.

For an existing draft, say it is the manuscript to edit. For your own writing, say it is a voice sample. For someone else's blog, say whether it is evidence or inspiration.

A path inside the Tart VM must point to a file inside the VM; files on your host Mac are not automatically available there. PDF and Word extraction depends on the tools available in that CLI. An unreadable file or link should produce a clear limitation, not a claim that it was read.

## Where your work goes

The default author workspace is `.blog-studio` inside the folder where you launched the CLI. For this pilot, that means a separate workspace under the `codex` or `claude` test folder. Ask Blog Studio to show the exact saved file when you want to inspect it.

Keep test writing out of the skill installation directory. A Team Hub is a separate shared repository that must be created or joined explicitly. Core CLI sign-in does not connect Google Docs; test Hub sharing and Google workflows after the local writing walkthrough, using deliberately selected test content and destinations. See [Team Hub](team-hub.md) and [Google Docs](google-docs.md).

## If something fails

If the skill is missing, first start a new CLI session. From Terminal in the VM, check setup with:

```sh
sh /Users/test-admin/Downloads/Blog-Studio/blog-studio-setup/installer/install.sh check --target both
```

Report the failed step, which CLI you used, the exact prompt, and the response or error. Include the article ID and whether its saved file exists. Avoid including credentials or private source content in the report.

A useful test note looks like this:

```text
CLI: Codex or Claude Code
Step: outline / draft / edit / resume / voice / file intake
Prompt:
Expected:
Observed:
Saved article ID and path:
Pass, fail, or unclear:
```

File placement and sign-in are already verified for this VM. This walkthrough tests the remaining behavior: discovery, helpful conversation, correct stopping points, faithful use of sources, and saved continuity.

## New convenience commands (runtime 1.3.0)

In the CLI conversation, try these plain-language requests:

1. “Check my Blog Studio setup.” Expect a short readiness report. Missing optional
   Google connectivity should not prevent local writing.
2. “Show my blogs.” Expect article names, stages, last activity, and next steps for
   the current workspace; an empty workspace should offer a new start.
3. “Continue Handoff pilot.” Expect the saved article and exact pins, without
   repeating intake. Duplicate names should prompt a choice.
4. “What do you know about this article?” Expect selected sources/roles, voice,
   active article preferences, team context, and review state.
5. “Remember for this article: use descriptive headings.” Then “Correct that:
   use question headings.” Then “Forget that heading preference.” Expect the
   active preference to change while the draft and old history remain intact.
6. “Stop using that team rule in this article.” Expect only this article's
   selection to change; other users retain their selections.

Use the trusted 1.3.0 installer before testing these runtime commands. The guide
and candidate code in this checkout do not update a running installed session.
For a shared preference, explicitly say “for our team” and select a Team Hub.
Follow the [live acceptance protocol](live-acceptance.md) for Google and two-person
checks; those need actual connected tools and another authorized member.

## Browse shared blogs in GitHub

After using the 1.3.0 runtime to save or sync a selected Team Hub, open its repository
homepage. Follow an article title into `blogs/<author>/<title>/README.md`. Try the
outline, context, and history links. An article without a chosen author or voice
appears under Unassigned; ask Blog Studio to set its author when appropriate.

Ask Blog Studio to rename an article or change its author and sync. Its readable
folder should move, while the canonical history stays intact. Use Blog Studio for
edits: the generated GitHub pages are browsing views. For a review-required hub,
merge the authorized contribution before expecting new views on main.
