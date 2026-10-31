# The runner

The runner is the program behind the page. It keeps your workspace and takes each deck from its start to its delivery: a deck on the desk runs to the desk with no stops, except a look you chose to pick, and a gated deck stops each time it needs your decision. You work on the page in your browser. The runner starts your assistant for each piece of work, checks what comes back, and keeps it. Focused conversation work starts separately without a worker and can be handed to the runner deliberately.

## What you need

The installer brings the runner, offers the two companion skills, and says which of these this computer still lacks. The page checks again the first time it opens, and says in one sentence what is missing.

- Python 3.11 or newer, and git, set up with your name and email. For a repository your team shares, git must reach it without asking for anything: if `git clone` works for its address in a terminal without a question, the runner can use it.
- Claude Code or Codex, installed and signed in as you. The runner uses your own sign-in and has no key of its own.
- [harness-slides](https://github.com/dbbaskette/harness-slides-skill), which draws, checks and renders every slide, and [harness-research](https://github.com/dbbaskette/harness-research-skill), which does the research. The installer offers both, at the versions in `installer/companions.json`. Both need Node 20 or newer.
- Your brand skill. A deck is always made in a brand, and Presentation Studio names none of its own. Without one, a deck is made up to the first step that needs your brand, and waits there. See [the brand skill](#the-brand-skill).
- A way to turn slides into pictures: LibreOffice and Poppler on this computer, or Google access that reaches Drive.
- Google sign-in (gcloud), only for Google Slides as the output or a Google Doc as the input. Without it a deck is delivered as PowerPoint.

## Start it

On a Mac, double-click "Open Presentation Studio" in the Applications folder inside your home folder. A terminal window opens and the page opens in your browser. Anywhere else, run:

```bash
sh ~/.local/share/presentation-studio/studio
```

From a copy of the repository, without installing, it is `python3 runner/studio.py serve --open`.

The window prints one line with a link. The part after `#` is a key, and the page does not work without it. If you open the page yourself, use the link exactly as it was printed. The runner works for as long as that window is open: press Ctrl-C, or close the window, to end it. Nothing is lost. Start it again and every deck carries on from where its files say it is.

One runner serves on a computer at a time. The installer will not update, roll back or remove while it is open; the one exception is the runner's own upgrade, below.

`sh ~/.local/share/presentation-studio/studio status` prints what is set up and where every deck is, as JSON. It changes nothing and asks nothing online.

`sh ~/.local/share/presentation-studio/studio saved-work` prints, as JSON, which saved decks still need each older path the runner keeps for them: the legacy research question queue, the cover drawn for a brand skill that offers no looks, and the branches for a Harness Slides that lists no capabilities. Each path comes with the decks that need it and why, and `unused` lists the paths no deck needs. `--folder PATH`, given once or more, looks at a deck folder outside the workspace as well, such as one made in a conversation. Like `status`, it starts nothing, changes nothing and asks nothing online.

## Set it up

The first time, the page opens on set-up.

- **Where decks are kept.** The address of a repository your team shares, or a folder on this computer for trying things out. The runner keeps its own copy of the repository and writes only inside its `presentations/` folder. Each answer is checked as you give it.
- **When your team sees the work.** After each decision, or only when you press "Share now".
- **Your name, your assistant, the brand and the output.** The assistant comes with its model and how hard it reasons. The brand and variant are those your brand skill lists. The output is Google Slides or PowerPoint.
- **How slide previews are made**, with LibreOffice on this computer or through Google Drive, and **which brand skill to use** when there are several.

Nothing is changed until you save, and anything can be changed later in Settings. The values every studio shares are kept in one file for all of them: see [shared values](#shared-values).

## Make a deck

"New deck" opens the desk's start: one sheet in three numbered steps, **1. What you start from**, **2. Audience and goal** and **3. Research and settings**, then **What happens after Start**, with **Start** and **Cancel** together at its end. **Start a deck** on Home opens the same sheet with the kind of deck already chosen. Start checks every step and goes to the first answer still missing, in the order the sheet is filled; Cancel closes the sheet and keeps what you filled in for the session. A refusal from the runner is said under the steps, and every answer stays.

1. **What you start from**: an idea, a document or an existing deck, and the material itself. For an idea, the brief, "What should it cover? (optional)", of up to 4000 characters, which goes to the research plan and the outline. For a document, the document, as a file (.txt, .md, .html, .htm, .docx or .pdf), pasted text or a Google Docs link, with an optional line, "It lays out the slides" or "It is material to build from" (left unset, the document is read first to tell which). For an existing deck, the deck, as a .pptx or a Google Slides link, then its five levels (Brand only, Polish, Redesign, keep content, Full rework and Selected changes); Selected changes adds its box, "Which slides, and what to fix".
2. **Audience and goal**: the title, who it is for, what they should take away, about how long in minutes, and a talk or a handout.
3. **Research and settings**: research, on or off, with where it may look (your documents, your sites and/or the public web) and up to eight questions; an existing deck has no research. With research on, a deck from a document says its source document is included with the references. **Look** is "Pick it when the samples are drawn", the default, or "Use the brand's default look", for every kind of deck whose looks are drawn: an idea, a document, Redesign and Full rework. A line names the brand, variant and output the deck starts with, your defaults; **Brand, output and assistant** opens them, with the assistant and its model, to change for this deck alone. There is no review level and no first-draft choice.

Changing the kind of deck keeps everything typed and chosen, research and where it may look included. Each kind keeps its own file and link, and gets them back when it is chosen again.

**What happens after Start** is a short numbered list made from the choices on the sheet, and it changes as they do. It opens with what the deck waits for before the desk: "Before the desk, it waits for you twice: to approve the slide text, then to pick the look.", "… to approve the slide text.", "… to pick the look." or "It runs on its own until the deck opens on the desk." Then, as they apply:

- **Research.** When it is on; for a document left to the reading, only if the document turns out to be material to build from. A document marked "It lays out the slides" is not researched.
- **Approve the slide text.** For an idea, a document and Full rework: the titles, the words on each slide, their order and the speaker notes are drafted first, for you to read, ask for changes or choose **Approve text & design deck**. Nothing is designed until you approve. Brand only, Polish, Redesign and Selected changes have no new slide text: their line is "The changes are made", on a copy of your deck.
- **Pick the look**, after the text is approved where there is text, or **The brand's default look**, with no stop.
- **Review the deck** on the desk, and **Deliver**.

An existing deck with no level chosen yet says to choose how much changes first. It starts at once. Approving the text first applies to decks started from this sheet: a deck saved before keeps the decisions it was saved with, and starting the runner again asks for nothing a deck already passed.

### On the desk

A deck started from the desk's start runs the same steps as any other, with its stops met on the desk. It passes each stop before the deck with a receipt that says the desk continued it, never your approval, except its slide text, which waits for your **Approve text & design deck** wherever an outline is drafted. The research plan comes from the form's questions, the outline is the desk's Outline tab, and the look is the one you pick when its samples are drawn, the start's default, unless you chose the brand's default look, said as "You chose the brand's default look at the start".

- **Progress.** Nothing is needed from you: the first line says about how many minutes are left, from what each step took on this computer, and with no record yet it says "Nothing needed from you. The deck opens here when it is ready." and "This computer has no record yet of how long that takes." Below it are the step in hand, **Slides taking shape** with each preview as it is drawn, and a note box under each preview, "How should this slide change?" with **Send note**. Besides the slide text, where it is drafted, the look is the only pause, when you chose to pick it: "One thing needs you: pick the look. The deck is drawn in it." A question from the assistant, a step that failed or ran out of time, the spend limit and a team notice come first, above everything else.
- **The desk.** The deck arrives on the desk the first time it is ready, and the desk is its screen from then on. It has a card for each slide under its section, with the last picture, the words and speaker notes from the outline, and what the brand check and the review found on it. The toolbar has **Deliver**, the one filled button, **Download**, **Finishing** and **More**; the tabs are **Slides** and **Outline**. While desk work runs, the line above the desk says what it is ("Redrawing section 2 (slides 4 to 6)", or "Redrawing: 2 of 5 sections"), with **Stop**.
- **The slide note.** "How should this slide change?" with **Redraw slide N** redraws only that slide's section: the slides tool's composer is handed the note, and every other slide of the section is kept byte for byte as it was drawn. The deck is then put together, rendered and checked, and comes back to the desk. A note is sent to a composer once. The line under the box says the price first: "Redraws section 2 (slides 4 to 6); the other slides stay exactly as they are. Then the deck is put together, rendered and checked. Last time this took …", or, with no record on this computer, "This computer has no record yet of what it costs. Expect minutes, not seconds." Where this computer knows how long a slide note usually takes, it adds "Usually about N minutes here." A note on another section while one is redrawn is drawn in the same pass; a note on a slide being redrawn is kept on its card, to send when that ends. A cover, section or closing slide has no note box, because no composer draws it.
- **The whole-deck note.** "How should the whole deck change?" with **Redraw every section** asks every section with the note, three at a time, priced by what the last whole build took. **Stop** ends the jobs under way, keeps what was redrawn, puts the deck together from it, and leaves each slide not redrawn saying "Not redrawn: you stopped the whole-deck note." with **Redraw slide N**. A section that fails leaves the others done.
- **Words.** A slide's title, subtitle, points, caveat and source are boxes on its card, saved one second after the last key against the version the page read. Selecting words shows the selection bar, **Rephrase**, **Shorten**, **Expand**, **Fix** and **Ask…**, and a small words job rewrites that passage alone; Expand reads your sources. The new words are checked with the slides tool's outline check, put into the slide's drawn section, and kept only when the section still compiles and fits, with no composer job; the deck is then put together and rendered again. Words that do not fit are not saved: the card keeps them with "These words do not fit the slide as it is drawn." and offers **Redraw with these words**, at the slide note's price, or **Discard**.
- **Speaker notes** are their own box on each card, saved the same way, with no composer. The deck is put together and rendered again, since the notes page is written with the deck; edits made while it is put together join one pass.
- **History.** Before a slide's words or notes change, they are kept in the deck's `desk/versions/` folder, which your team shares: up to 20 versions a slide, one for each editing session. The slide's drawing and picture at that version go under `work/`, on this computer only. **History** compares a version's words with the words now, and its picture with the picture now where this computer has it. **Restore** brings back the words and, where this computer kept it, the drawing, with no assistant; without the drawing the words go back as typed words do. A restore is a version too.
- **The Outline tab** is the outline editor: rename, reorder, add and remove slides and edit their words, with the storyboard. **Save** checks the outline and draws again only the sections whose slides changed; the rest stay as drawn, and before Save it says "N sections change and are redrawn; the rest stay as drawn." with what they last took. A deck from a document says how it was read, with **Read it the other way**, priced; **Change the look** draws the looks again for a pick, then every section in the look picked, priced.
- **Add a source** takes a file or pasted text, listed under Sources. The words jobs, the speaker notes and the outline, when it is written again, read it; adding one starts no job and runs no research. With research on, the **Research panel** shows the findings and gaps: **Research again** reads the sources again, and **Leave out** redraws the outline and the look samples without researching again. Each says its price first.
- **Finishing** proposes, and nothing changes until **Apply**. **Brand check** shows the last render's check slide by slide, blockers first, and **Check again** runs the brand's audit on the deck as it is now, in seconds; Apply on a line redraws that slide's section with it as the note, priced. **Review the deck** runs the reviewer on the deck on screen, priced by its last review, and what it finds comes back on each slide as a proposal: **Apply** is a slide note made from the finding, and **Skip** keeps it as read. No section is sent back by itself. **Speaker notes** proposes notes for every slide from its words, the outline and your sources, each beside the notes it has, and Apply saves them with no redraw. **Rehearse**, counted here with no assistant, says how long each slide's notes take at 150 words a minute and the total against your minutes: "Slide 4's notes take about 2 minutes; the deck's notes take about 31 of your 25 minutes."
- **Deliver** is the brand's final check and always yours. It sends the deck on screen and is refused while a change is still being made ("Your last change is still being put together. Deliver when it is done."). When the brand check found blockers, a sheet lists each with its slide: "The brand check found 2 problems that block delivery. Deliver anyway, or fix them first." **Deliver anyway** is bound to the list you were shown; a list that changed since is refused, to look again. The sheet says whether the deck was reviewed, and deliver.json records it; a desk deck's title and file are never labelled a first draft.
- **Revisions.** A change to a delivered deck sets its delivery aside and makes the next revision: "Delivered as revision 2. A change here makes revision 3, delivered when you press Deliver." The delivered revision stays in the deck's revisions.
- **An existing deck** comes to the desk at its five levels. At every level but Full rework each card shows the slide's **Before**, as it was in your deck. **Brand only** and **Polish** keep your deck's words exactly: a word edit, a selection and a redraw with new words are refused with "This deck keeps your own deck's words exactly. Change them in your deck, or start again at Redesign, keep content." Speaker notes are still edited, and a note that changes only how a slide is drawn still works. **Selected changes** changes your deck's text through `pptx patch` to a copy, checked by `pptx compare`, and never the deck itself: a typed or selected change in one part of a slide is one operation of the plan, and a note on a slide plans its changes again. Its speaker notes are kept as they are, and it has no whole-deck note, Outline tab or Finishing.
- **Open on the desk.** A gated deck that is delivered offers **Open on the desk** on its screen, beside **Send to Google Slides**. It needs this computer's last drawing of the deck, or at Selected changes its plan and copy; without it, it says "There is no drawing of this deck on this computer. Draw it here first, or open it on the computer that made it." Opening keeps one version of each slide's words, leaves the gates the deck passed as they were and leaves the delivery as it is: the revision delivered stays delivered until a change is made, and the first change makes the next revision. From then on it keeps no review level and is reviewed only from Finishing, as every desk deck is; a look drawn again is picked by you, or is the brand's default where its level chose that. Notes left from its gated stops are set aside, never drawn with a later change. Opening it again changes nothing.
- **A teammate's computer.** Every desk change goes through the team claim, and desk work runs only on the computer that drives the deck. A computer without the deck's `work/` never redraws it unasked: the desk shows the shared words with "There is no drawing of this deck on this computer." and **Draw it here**, priced by the last whole build.

### Gated decks

A saved deck started before the desk can keep the gated flow, with the review level saved for it. This part describes gated decks. Review levels govern only these saved decks, and Training Studio.

| You start from | The runner stops for you at |
| --- | --- |
| An idea | The research plan and the research, if you turned research on; the outline; the look; the deck |
| A document | Whether it lays out the slides or is material to make them from; the research, for material with research on; the outline; the look; the deck |
| A deck | Its slides, as pictures; then what the level you chose needs: the new outline (full rework), the look (redesign and full rework), and the deck |

These are Step by step's stops. A gated deck retains its saved level: Balanced reads the direction (the research, the outline and the look together) and then the deck, or, for a Redesign that keeps its content and so has no outline stop, the look and then the deck; Automatic draft only the deck, in the brand's default look. Between its stops a deck carries on by itself, and each step it continues is recorded as the level's, never as your approval. Balanced's direction review is approved only with a look picked from the samples shown: edit the outline there and its looks are drawn again, for you to choose from before the build, and a previous pick is marked for you, never applied to samples you have not seen. Every level stops at the deck. **See the first draft before the deck is checked**, under Options on the form, builds and renders the deck without its check and repairs: it stops as **First draft, not checked**, where **Check the deck** runs them and **Use this first draft** takes it as it is, and a deck delivered that way says **Delivered: first draft, not checked**. Undo the last step is offered only while that step is this deck's and not shared yet, and reading a document the other way at the direction review says what it redraws, and its price, before it is sent. Once it runs, a line under the deck's stages says how many steps are left, where it next stops and what it has cost so far, and every **Ask for changes** says what is drawn again and what that took the last time.

At each stop the page shows what was made: the text, or the real slides in a slide viewer with the contact sheet, the brand's own check and the review's notes. A redesign shows each slide before and after. Beside it the page says what approving does, and **Approve** does it at once, with no second question. Or **Ask for changes** in your own words; the runner makes them and brings the new version back. At the deck, each slide has its own "Ask for changes".

**The research and the outline, item by item.** The research plan, the findings and the outline are lists to mark: drop or reword a question, research a finding again or leave it out, ask for changes to one slide, add a question. Nothing is sent until you press the button at the foot of the list, which says what it will do: **Approve** when nothing is marked; **Approve without 2 questions** (or **Approve, leaving out 1 finding**, or **Approve with every finding** when you bring back every finding left out earlier) when what you marked needs no assistant, which is applied and approved in one click; **Send 3 changes** when something must be redone, which comes back to you. A line beside the button counts what you marked. The findings that need a look are under **Look at these first** and the answered ones under **Answered**; a slide's points and notes open under **Points and notes**; the whole plan and report stay a click away, under **Read the full plan** and **Read the full report**. The last question cannot be dropped, and the last finding kept cannot be left out, since research needs a question to look up and the outline needs a finding to draw on. Up to 10 questions can be added at once, and a plan holds at most 30; research done as one report and one independent check holds at most 8, and the page says how many more it takes. A question added at that research stop runs the investigation again, priced before it is sent. A question added after the research is researched on its own, and the other findings are kept.

### Every deck

**The research check.** Research for a deck is written by one assistant and checked by another, for up to three rounds of correction. The check reads every source the report quotes and, for a document you supplied as a PDF, a Word file or a web page, the file itself as well, with its size and fingerprint, so that it can say it read both; a Google Doc, a text or a Markdown document is its own text. If the check says it could not read a document it must vouch for, the studio reads it the same way itself: when it can, the next round's check reads it; when it cannot, the research stops after that round and says it is the studio's problem, not the research's, and **Try again** works once the document can be read. When the check still objects after the third round, the stop counts its objections by what they are about, with the first of each, and says what the rounds took; every objection is listed under its group in `research/review.md`.

**The look.** Before any slide is designed, the brand draws one slide of the outline in each of its looks, side by side, through harness-slides' own preview route. No assistant is used for it. You pick the look every slide is drawn in, in your own words if you like: it sets the colours, what each colour means and how cards are drawn on every slide. **Choose another brand** offers the brands and variants your brand skill lists; the looks are drawn again in the one you choose. If the looks cannot be rendered here, **Try again** draws them again, and **Carry on in the brand’s default look** goes on knowingly, with the deck marked as an unreviewed draft of its look. When the deck is built, each slide's layout is designed on its own from what it says, in the look you chose.

**Delivery.** The deck is delivered as Google Slides, or as a PowerPoint file to download. A PowerPoint delivery is kept beside the deck as `deck.pptx` and shared with it, so a teammate's computer can download it too; a new delivery replaces it. A delivery made before that stays on the computer that made it, and the page says so. An existing deck is never changed: you always get a new copy. On a gated deck, asking for changes to a delivered deck draws again the sections that hold the slides you name (every section when you name none), reviews the deck again and delivers a new numbered revision. A deck delivered as a PowerPoint file, whether PowerPoint was chosen or Google was not connected, can be sent to Google Slides later, unchanged, with **Send to Google Slides** on its screen: the saved deck goes as the next revision, nothing in it is built again, and the form's original output choice is kept. Status → Check this computer says whether Google is signed in on this computer, and how to sign in. A gated deck that is delivered can also be opened on the desk, as above. On a gated team deck, the computer that delivered it can ask for changes directly: the confirmation says the deck will run here again, and the request takes the deck back before changing it. A teammate takes it first.

**Watching a run.** A deck's run shows every step, how long each took and what it cost.
- **Pause**: the step in hand finishes and nothing new starts until you resume. **Stop**: the work in hand is ended; everything already kept stays.
- **Try again**, when a step failed. A step is tried up to three times, each time with the reason the last one failed; then the deck stops, and Try again runs that step again from the start. A slide build keeps the sections already drawn. Research done as one report and an independent check continues from its saved draft and runs up to three more rounds, and the stop says what the last rounds took. **Undo** takes back the last thing done to the deck, while it is not shared yet.
- **Give it more time and try again**, when a step ran out of the time a step may take. The stop says so, with the minutes, and that the limit is in Settings, under Limits. This lets each step of this deck take twice as long and runs the step again; the deck keeps that time when it carries on. Raising the limit in Settings is the other way on, for every deck.
- **Check this computer**, when the assistant could not be used: it is not installed, not signed in or out of reach. The deck stops at once, without spending tries, and the stop says to use Check this computer on the Status screen.
- **Wait, then Try again**, when the assistant's account reached a usage or rate limit. The deck stops at once and says so; Check this computer cannot show such a limit, so the stop does not send you there.
- **Answer a question**: an assistant that needs something only you know can ask, and the run waits.

A deck that has spent what it may stops and asks before spending more, and so does one with too little left to start a step: no job is started with less than $0.50 to spend, or a quarter of a limit under $2.00. A step stopped mid-way because it spent what was left is not counted as a failed try: the deck stops in the same way, and the step starts again when you carry on. **Resume** lets it spend as much again; raising the limit in Settings, under Limits, is the other way on, and the stop says both. You can close the page while decks work: Home says what needs you, and with "Tell me when no page is open" in Settings, this computer's own notifications do too.

## Keeping it current

Each time the runner starts, and when you press "Check this computer again" on the Status screen, it checks that Presentation Studio and the two companion skills are in place and current. The page opens at once; the checks run behind it.

- **Links it puts back.** If a link the installer placed has gone (in an assistant's skill folder, to the installed version, or the `studio` and `presentation` commands), the runner puts it back. It puts back only what the installer placed, where it placed it. Anything else in the way is left alone and said.
- **The companion skills.** Each is compared with the version this Presentation Studio was made with. One that is missing, or older than the oldest version Presentation Studio accepts, is shown with "Update the skills", which installs exactly the version it was made with. Nothing is fetched until you say yes. The update runs the installer's own pinned and checked install, in the background, and is refused while a deck on this computer is working.
- **Newer releases.** Once a day, unless "Look for updates once a day" is off in Settings, the runner reads the release tags of Presentation Studio, each companion and your brand skill with `git ls-remote`. Nothing is downloaded or run. A companion released beyond what Presentation Studio is pinned to is shown, and never offered.
- **Upgrading Presentation Studio.** When a newer one is out, Home offers "Upgrade". After your yes, that version is fetched and its own installer checks it and installs it beside the one you have; then "Restart" opens it at the same address. It is refused while a deck is working. A runner started from a copy of the repository upgrades nothing: run `git pull` there.

### The brand skill

A brand skill you install yourself is found in the usual skill folders and used. Naming its repository adds installing and upgrading it from the page.

- In Settings, "Brand skill" takes the repository's address and which release to use (empty for the newest). "Check and save" reads its release tags as you, with your own git access and no questions, and keeps nothing until that works. The repository and release are shared by every studio.
- The Versions table has a row for it. When it is missing or a newer release is out, Home offers to install or upgrade it. Nothing is fetched or run before your yes, and it is refused while a deck is working or a companion waits for "Update the skills".
- Its own installer runs it. If that installer would replace your harness-slides with an older one, nothing is run and the page says so. Afterwards this computer is checked again, so the brand skill is found.
- The repository is your choice, so there is no pin to check a release against. Install only from a repository you trust.

## Shared values

Presentation Studio, Training Studio and Blog Studio keep the values they share in one file, `~/.config/studios-config.json` (`STUDIOS_CONFIG` names another place), and nowhere else. Change one of these values in any studio and all three use it from their next read. [The shared studios convention](shared-studios.md) describes the file and its rules, identically for every studio.

| Key | In Presentation Studio | Saved from |
| --- | --- | --- |
| `team.repository` | The team repository. Set-up offers it where this computer has joined none, and Status and Settings say when it is not the one this computer's workspace is a copy of. | Set-up, when it joins another team repository |
| `team.branch` | The branch, for a new workspace in that repository. A workspace your team has set up already keeps the branch its `hub.json` names. | Set-up, with a new team repository, where the file names no branch for it |
| `share` | `"decision"` shares after each decision, `"asked"` only when you ask. Any other value is `"decision"`. Used only for a team repository. | Set-up, for a team repository |
| `person.name` | Your name, as your teammates see who runs a deck and who decided what. | Set-up and Settings |
| `assistant.agent`, `.model`, `.effort` | The default assistant, its model and its reasoning level. A value Presentation Studio would refuse is its built-in default: Claude Code, with the model and level left to it. | Set-up and Settings |
| `brand.repository`, `.release` | Where the brand skill is installed and upgraded from. An address that carries a password or token is refused, and a release needs a repository. | Settings, "Brand skill" |
| `brand.brand`, `.variant` | The brand and variant a new deck is offered first, when the brand skill on this computer has them. | Set-up and Settings |
| `output` | `"google"` makes a new deck Google Slides, `"pptx"` PowerPoint. | Set-up and Settings |

- **Saving writes only what changed.** Only the values you changed on that screen are written, and only where the file says otherwise. Everything else in the file, including what other studios keep there, stays as it was, byte for byte. The file is replaced whole or not at all. If another studio changed a value while the screen was open, a value you left alone stays as it set it, and a change of yours to that same value is refused, with a sentence saying to look again and save. The studios take turns writing the file, through the lock beside it, `studios-config.json.lock`. A folder on this computer is not a team repository, so it never writes `team` or `share`.
- **What stays here.** The limits, how slide previews are made, how many decks run at once, which brand skill to use when there are several, notifications and looking for updates belong to Presentation Studio on this computer alone, in its own settings.
- **When the file cannot be read.** Presentation Studio carries on with its built-in defaults, says so in one sentence on set-up and Status, and refuses to save a shared value until the file can be read. It never writes over the file.
- **When the team repository changes elsewhere.** The workspace you joined is a copy of a repository, kept in Presentation Studio's own data folder. If another studio changes `team.repository`, Presentation Studio carries on in the copy it has and never moves by itself. Status and Settings say that your studios now share another repository, with "Join it", which opens set-up filled in with it. Joining writes the repository, and its branch, into the shared file.
- **From an earlier version.** Earlier versions kept some of these values on this computer. When the runner starts, it writes each of them into the shared file where the file has none, with the team repository and branch this computer joined, and then removes them from its own settings. A value the file already has is left as it is, and Status and Settings say once which ones those were, until you choose "Got it". A model and a level move only beside the same agent, a release only beside the same repository, and a variant only beside the same brand. While the file cannot be read nothing moves, and it is tried again at the next start.

## With a team

When your decks are kept in a repository your team shares, several people work in the same `presentations/` folder, beside Training Studio's `trainings/` and Blog Studio's `blogs/`. One rule keeps them from treading on each other: **each deck is run from one computer at a time.** None of this applies to a folder on one computer.

- **Who runs a deck.** Starting a deck makes it yours: your name and this computer are recorded in it, and that is shared before any work is done. On every other computer it is listed under "Run by your teammates", read-only, with when it was last shared.
- **Taking over and handing over.** "Take it over" makes a teammate's deck yours; their runner stops working on it the next time it looks, and keeps anything it had not shared out of the way, where git can bring it back. "Hand over" lets go of your deck so anyone may take it. A finished deck has no driver: anyone can read and publish it, and "Take it" makes it yours again.
- **Every decision is a commit.** Sharing happens after each decision, or when you press "Share now", as you chose. A push is never forced.
- **If two computers disagree.** When the same deck was changed on two computers anyway, sharing stops and nothing is overwritten. "Carry on from the shared version" sets this computer's unshared commits aside under a ref of their own, says where, and carries on from what the team has.
- **When the repository cannot be reached,** your work is kept and labelled "not shared yet", and goes with the next share.
- **Publishing** marks a finished deck, as it stands, as its next numbered revision.
- **What is shared.** The deck's text, decisions, brand contract, Google Slides link and a small contact sheet. Uploaded files, the original deck, slide pictures and renders stay on the computer that made them (`sources/` and `work/` are never committed).
- **A deck made in a conversation** with `/presentation-studio` keeps the same folder and run record as one the runner makes. The runner can copy such a deck into its workspace and carry on from what its record says, leaving the original folder as it was; the page offers it as **Bring in a deck**, on Decks, for the decks this computer remembers: pick one, then **Bring it in**. A deck the runner drives is never also driven from a conversation.

## Research you can review

The stop shows the authored brief first, the check's acceptance and note, gaps, partial
sources, source counts and findings mapped to your planning questions. Report and evidence
remain available in folds. An unreadable bundle leaves the saved report readable without
claiming that its check accepted it.

**Research needs synthesis.** Research for a new deck is done by a Harness Research that can
synthesize, 1.0 or newer. On one that cannot, **Start** refuses a deck with research on, with
nothing made: "Research needs Harness Research 1.0 or newer on this computer, and the one
here cannot do it. Update Harness Research, then start again." A deck with research off
starts as before.

**Where research may look.** Research from your documents, your sites and/or the public
web: the form's **Research from**, a row of ticks, offers *your documents* (a deck from a document, on by
default), *your sites* (the shared list from Shared settings, prefilled, a tick for each site
and **Add a site for this piece of work**, which does not change the shared list) and *the
public web*. At least one that applies must be on. A deck from a document starts with your
documents only ("With your documents only, nothing about them is searched for on the public
web."), one from an idea with the public web; your sites stay off until they are ticked.
Your sites are searched with the assistant's own web search tool, and only pages from under
them are saved. A site added for one deck is checked by the runner (`/api/research-site`)
with the same rules as the shared list, and its refusal is said beside the box. The deck keeps the
choice as `research_from` (`{"documents", "sites", "web"}`) in its form, with the exact list
it started with, and its stops line says it: "Research from your documents and 2 of your
sites (…)". A deck saved before this reads its `research_sources` as before: `documents` is
your documents, `both` your documents and the public web, and research with neither, the
public web (with a document's own documents).

Every page a research job saves is checked on every hop, redirects included, and each hop
is checked and asked for without its fragment, so a `#` cannot carry a path past the check.
With your
sites on and the public web off, a page is saved only when it is https on a listed site's
own host (no subdomain or lookalike) and under its path at a segment boundary; any other
page is refused with a sentence naming the sites, and the research stop says how many were
("2 pages were outside your sites (docs.example.com) and were not saved."). With the
public web on, any public page may be saved. Private and local addresses are refused in
every case. The worker is told to search the listed sites first, with `site:` queries or a
site's own search page, and the research task's scope names the allowed sites. Harness
Research's source mode is `selected` for your documents alone, `mixed` for your documents
with your sites or the web, and `public` otherwise; the plan's scope is `supplied-only`
unless research saves pages, when it is `public-web`.

Supplied-only synthesis writes
its plan from at most eight optional form questions (300 characters each), without a
planning job. Web synthesis asks at most eight questions together; legacy queues keep 30.
An explicit plan revision uses the planning assistant with the saved questions and your
request, retaining the selected source boundary and question limit.
Existing decks retain their saved scope and pipeline.

Ask about this finding adds a note to the whole research request, whose sheet says what
rounds it may run, its last recorded cost and the made work it will redo. At the Balanced
direction review, Leave out selects findings for a new outline and new looks without
rerunning research; on the desk, the Research panel's **Leave out** does the same. The full
reviewed bundle stays intact.

## The companions, as the runner uses them

- **Versions.** A deck needs Harness Slides 0.16.0 or newer, the version the installer pins,
  and a brand skill of 0.14.0 or newer, for its look samples and talk-or-handout export. An
  older Harness Slides is refused when a deck needs it, in the same words on Status and at
  the step; when the brand skill's own installer brings that very version, Status says so.
  An older brand skill is a Status line, and it stops a new deck at its first step that
  needs the brand, with a sentence saying to update it in Settings; a deck whose brand was
  exported already carries on.
- **The review.** The reviewer answers the slides tool's own questions, as each whole-deck
  preview writes them in `critic.json`; a round keeps the questions it was asked, and a
  review is reused only for a round asked the same ones. The reviewer also reads the slides
  tool's review guidance and the brand's review checklist, when the brand gives one.
- **The brand's check before the review.** After each round's preview the brand checks the
  deck. A blocker on a slide sends that slide's section back to be drawn again, within the
  two repair rounds, as a reviewer's finding does on a gated deck; a warning goes to the
  reviewer. On the desk, a review's findings are proposals in Finishing instead. A check
  that cannot run leaves the round as it is, with a note. The delivered deck is checked
  again, as before, and the deck's stop shows that result.
- **Code spans.** Outline writers and composers write a configuration field, command, API
  or file name as a code span, with plain English first; a title takes none.
- **Pictures.** At the outline stop a cover, section or content slide can be given a
  picture of your own: a PNG or JPEG of up to 20 MB, what it shows and where it came from.
  It is recorded in the deck's asset project with the slides tool's `assets add-supplied`,
  drawn by its asset ID, and checked again before the deck stop. No picture is generated.
  "Remove the picture" takes it off its slide (`/api/picture-remove`); the tool's record
  stays, so a picture given again, or a retry after a record that failed part way, takes a
  new asset ID. What it shows and where it came from go joined to `--alt=` and `--source=`,
  so words that begin with "-" are kept.
- **Previews.** Previews through Google Drive, on a slides tool with a preview pool, run side
  by side, up to `HARNESS_PREVIEW_POOL_SIZE` (4 when unset); LibreOffice renders one at a
  time.
- **Fonts.** Status says when the brand's own check finds no Arial on this computer. It holds
  no deck up.
- **Redesign, keep content.** "Redesign, keep content" has no design session. The extracted outline is approved at the outline stop, the look is chosen from rendered samples, and per-slide changes are asked for at the deck stop by marking slides. The brand's "content-preserving redesigns use a per-slide walkthrough" is not followed: Presentation Studio has no design gate, and porting Training Studio's is its own project.
- **Research.** Writers are told what the reviewed research is, and that its IDs and digests
  are never words a reader reads. A goal that compares options asks the research for a
  comparison. **Bring the evidence up to date**, at the research stop, reads the sources
  again. The legacy question queue is kept for a deck begun before the synthesis research contract, so that it finishes as it began; a new deck never starts on it. It can go once no workspace holds such a run: `studio saved-work` lists any deck that still needs it.

## What the runner guarantees

- **Only you approve.** A deck moves past a stop only by your decision on the page. Neither the runner nor an assistant can approve for you: a step its review level carries on past is recorded as the level's, never as your approval.
  On the desk, the steps before your deck run as your start chose. Delivering is always yours.
- **An assistant cannot touch your files.** Each one works in an empty folder outside your decks, with no shell and no file tools, only the runner's own tools. The runner checks what it hands back before anything is kept.
- **Slides are made by harness-slides,** with your brand's exported contract. The studio never edits a slide file itself.
  On the desk, a word or speaker-notes edit is put into the section's drawing as its composer handed it in, and kept only when harness-slides compiles it and every approved word is there; otherwise nothing is saved, and the slide can be redrawn with the new words.
- **Your original is never changed.** An existing deck is read, and you always get a new copy.
- **Everything is recorded.** Each step, decision and request for changes is a commit in the workspace.
