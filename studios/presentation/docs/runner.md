# The runner

The runner is the program behind the page. It keeps your workspace, takes each deck from its short form to its delivery, and stops each time it needs your decision. You work on the page in your browser. There is no conversation with an assistant: the runner starts your own assistant for each piece of work, checks what comes back, keeps it, and waits for you at each stop.

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

## Set it up

The first time, the page opens on set-up.

- **Where decks are kept.** The address of a repository your team shares, or a folder on this computer for trying things out. The runner keeps its own copy of the repository and writes only inside its `presentations/` folder. Each answer is checked as you give it.
- **When your team sees the work.** After each decision, or only when you press "Share now".
- **Your name, your assistant, the brand and the output.** The assistant comes with its model and how hard it reasons. The brand and variant are those your brand skill lists. The output is Google Slides or PowerPoint.
- **How slide previews are made**, with LibreOffice on this computer or through Google Drive, and **which brand skill to use** when there are several.

Nothing is changed until you save, and anything can be changed later in Settings. The values every studio shares are kept in one file for all of them: see [shared values](#shared-values).

## Make a deck

"New deck" asks how you are starting, then a short form: the title, who it is for, what it should achieve, roughly how long, the brand and variant, and the output. It starts at once.

| You start from | The runner stops for you at |
| --- | --- |
| An idea | The research plan and the research, if you turned research on; the outline; the look; the deck |
| A document | Whether it lays out the slides or is material to make them from; the research, for material with research on; the outline; the look; the deck |
| A deck | Its slides, as pictures; then what the level you chose needs: the new outline (full rework), the look (redesign and full rework), and the deck |

These are Step by step's stops. The last step of the form chooses, in **Where this deck stops**, the level for this deck: Balanced reads the direction (the research, the outline and the look together) and then the deck, or, for a Redesign that keeps its content and so has no outline stop, the look and then the deck; Automatic draft only the deck. Undo the last step is offered only while that step is this deck's and not shared yet, and reading a document the other way at the direction review says what it redraws, and its price, before it is sent. **Use this for new work in every studio** also makes it the shared level when the deck starts; **Settings** has **Where new work stops**. Once it runs, a line under the deck's stages says how many steps are left, where it next stops and what it has cost so far, and every **Ask for changes** says what is drawn again and what that took the last time.

At each stop the page shows what was made: the text, or the real slides in a slide viewer with the contact sheet, the brand's own check and the review's notes. A redesign shows each slide before and after. Beside it the page says what approving does, and **Approve** does it at once, with no second question. Or **Ask for changes** in your own words; the runner makes them and brings the new version back. At the deck, each slide has its own "Ask for changes".

**The research and the outline, item by item.** The research plan, the findings and the outline are lists to mark: drop or reword a question, research a finding again or leave it out, ask for changes to one slide, add a question. Nothing is sent until you press the button at the foot of the list, which says what it will do: **Approve** when nothing is marked; **Approve without 2 questions** (or **Approve, leaving out 1 finding**, or **Approve with every finding** when you bring back every finding left out earlier) when what you marked needs no assistant, which is applied and approved in one click; **Send 3 changes** when something must be redone, which comes back to you. A line beside the button counts what you marked. The findings that need a look are under **Look at these first** and the answered ones under **Answered**; a slide's points and notes open under **Points and notes**; the whole plan and report stay a click away, under **Read the full plan** and **Read the full report**. The last question cannot be dropped, and the last finding kept cannot be left out, since research needs a question to look up and the outline needs a finding to draw on. Up to 10 questions can be added at once, and a plan holds at most 30; research done as one report and one independent check holds at most 8, and the page says how many more it takes. A question added at that research stop runs the investigation again, priced before it is sent. A question added after the research is researched on its own, and the other findings are kept.

**The research check.** Research for a deck is written by one assistant and checked by another, for up to three rounds of correction. The check reads every source the report quotes and, for a document you supplied as a PDF, a Word file or a web page, the file itself as well, with its size and fingerprint, so that it can say it read both; a Google Doc, a text or a Markdown document is its own text. If the check says it could not read a document it must vouch for, the studio reads it the same way itself: when it can, the next round's check reads it; when it cannot, the research stops after that round and says it is the studio's problem, not the research's, and **Try again** works once the document can be read. When the check still objects after the third round, the stop counts its objections by what they are about, with the first of each, and says what the rounds took; every objection is listed under its group in `research/review.md`.

**The brand.** Before any slide is designed, the runner draws the deck's cover in the brand you chose, so you can see it is the right one. No assistant is used for it, and nothing about the slides is chosen there. **Choose another brand** offers the brands and variants your brand skill lists; the cover is drawn again in the one you choose. When the deck is built, each slide's layout is designed on its own from what it says, in the brand's own colours.

The deck is delivered as Google Slides, or as a PowerPoint file to download. A PowerPoint delivery is kept beside the deck as `deck.pptx` and shared with it, so a teammate's computer can download it too; a new delivery replaces it. A delivery made before that stays on the computer that made it, and the page says so. An existing deck is never changed: you always get a new copy. Asking for changes to a delivered deck draws again the sections that hold the slides you name (every section when you name none), reviews the deck again and delivers a new numbered revision. A deck made as a PowerPoint file because Google was not connected can be sent to Google Slides later, unchanged, with **Send to Google Slides** on its screen. Status → Check this computer says whether Google is signed in on this computer, and how to sign in.

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
- **A deck made in a conversation** with `/presentation-studio` keeps the same folder and run record as one the runner makes. The runner can copy such a deck into its workspace and carry on from what its record says, leaving the original folder as it was; the page does not offer this yet. A deck the runner drives is never also driven from a conversation.

## What the runner guarantees

- **Only you approve.** A deck moves past a stop only by your decision on the page. Neither the runner nor an assistant can approve for you.
- **An assistant cannot touch your files.** Each one works in an empty folder outside your decks, with no shell and no file tools, only the runner's own tools. The runner checks what it hands back before anything is kept.
- **Slides are made by harness-slides,** with your brand's exported contract. The studio never edits a slide file itself.
- **Your original is never changed.** An existing deck is read, and you always get a new copy.
- **Everything is recorded.** Each step, decision and request for changes is a commit in the workspace.

## Research you can review

The stop shows the authored brief first, the check's acceptance and note, gaps, partial
sources, source counts and findings mapped to your planning questions. Report and evidence
remain available in folds. An unreadable bundle leaves the saved report readable without
claiming that its check accepted it.

**Where research may look.** Research from your documents, your sites and/or the public
web: the form's **Research from** offers *your documents* (a deck from a document, on by
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
rerunning research. The full reviewed bundle stays intact.

## The companions, as the runner uses them

- **Versions.** A deck needs Harness Slides 0.16.0 or newer, the version the installer pins,
  and a brand skill of 0.14.0 or newer, for its look samples and talk-or-handout export. An
  older Harness Slides is refused when a deck needs it, in the same words on Status and at
  the step; when the brand skill's own installer brings that very version, Status says so.
  An older brand skill is a Status line, and a new deck waits at its brand step.
- **The review.** The reviewer answers the slides tool's own questions, as each whole-deck
  preview writes them in `critic.json`; a round keeps the questions it was asked, and a
  review is reused only for a round asked the same ones. The reviewer also reads the slides
  tool's review guidance and the brand's review checklist, when the brand gives one.
- **The brand's check before the review.** After each round's preview the brand checks the
  deck. A blocker on a slide sends that slide's section back to be drawn again, within the
  two repair rounds, as a reviewer's finding does; a warning goes to the reviewer. A check
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
  again. The legacy question queue is kept for a deck begun before the synthesis research contract, so that it finishes as it began. It can go once no workspace holds such a run.

## Finish from the page

A deck from scratch has an optional brief for points, examples or a rough order, limited to 4000 characters. It goes to the research plan and outline. Research first, when on, asks where research may look: your documents, your sites and/or the public web.

Balanced direction approval needs a look picked from the samples shown. If you edit the outline, its looks are drawn again and you choose from the new samples before building. A previous pick is marked for you, never applied to unseen samples.

After delivery, the computer that made a team deck can ask for changes directly. The confirmation says it will run here again, and the request reclaims the deck before changing it. Teammates still take it explicitly. A deck delivered as PowerPoint can later use **Send to Google Slides** when Google is connected, whether PowerPoint was chosen or used because Google was unavailable. This sends the saved deck as the next revision and keeps the form's original output choice.
