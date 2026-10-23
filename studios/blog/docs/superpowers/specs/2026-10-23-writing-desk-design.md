# The writing desk: design

**Date:** 2026-10-23. **Owner's words:** "when i get the draft in handoff... there doesnt seem
to be a good way to give notes and have it rewritten. Look in to blog forge and see how it
did things.... it seems like we are getting overly complicated. We might need to step back.
Remove all the Voice stuff for now and focus on writing quality blogs or docs of different
types." Then: "(1) we choose the type of writing (2) we then add any relevant source docs,
urls, etc, set a few things like length etc like we already do and then we get a blog then
we should offer some of the blog forge editing", "an optimal flow for having a system that
can edit, co-author, or author blogs for you", "we should be able to add docs or urls as
sources for all cases", and "post processing would be the other things blog forge did...
Humanize, apply a voice, etc."

## Why

A new blog today runs a gated pipeline (angles, research plan, research, claims map,
outline, draft, review, handoff) with review levels deciding where it stops. Once a draft
exists, there are three separate ways to change it (Ask for changes at a gate, the
manuscript editor, the Tools sheet). The gate's "Ask for changes" says it rewrites but makes
a minimal edit, it is buried after Finish, the editor replaces the run's stages, and Revise
mode has no place for notes. Voice learning adds a library of author tools on top.

BlogForge, the owner's earlier tool, felt better to edit in because a draft was one page of
section cards with a notes box under each, a whole-draft note, selection edits, and quiet
version history; reviews were optional previews you applied. This design brings that shape
to Blog Studio within this repository's rules (standard-library Python, plain JavaScript,
no build step).

## The flow

Three ways of working share one path. Only where the work starts differs.

| You bring | Way of working | Starts with |
| --- | --- | --- |
| A topic | Author | Angles (optional), outline and draft written for you |
| An outline or notes | Co-author | A draft from your outline, or an outline shaped with you |
| A draft | Edit | Your draft on the desk, with an optional first pass |

Every way can take sources: files, links, Google Docs and team library posts.

### 1. What are you writing?

Cards for the kinds of post (the eight starters in `assets/styles/` and saved styles),
each with its usual length and shape. Choosing one pins the style as today.

### 2. What do you have?

- **Just a topic.** Title, audience, and the point to make: type it, or press **Suggest
  three angles**. Angles run as one job that reads the chosen sources and returns three
  cards (headline, point, who it is for) on the same screen. The person picks one and may
  edit its wording, or types their own point. This happens before Start, so it is not a
  stop.
- **An outline or notes.** Paste or upload. Choose **Write from my outline** (draft next) or
  **Shape an outline with me first** (an outline is proposed and opens on the desk).
- **A draft.** Paste, upload or a Google Doc (every tab, as today). Choose a first pass:
  **Tighten and proofread**, **Reshape to fit this kind of post**, or **Leave it as it is**.

### 3. Sources and settings

Files, links, Google Docs and team library posts with their roles (facts, approved
messaging, example of the kind of post), **Search my sites** and **Search the web too**
(both off by default; they use the existing research path, including the saved site list),
**Length** (usual for this kind, short, in depth) and **Tone**.
Then **Start**.

### Progress

One screen whose first line answers whether the person is needed: "Nothing needed from
you. The draft opens here when it is ready, in about N minutes." Below it, the current
step in plain words (reading sources, researching, outlining, drafting) and one clock for
the whole start. There are no stops. **Shape an outline with me first** ends by opening
the outline on the desk.

## The desk

The draft opens as one page: title, opening, then a card per section (heading and text).

- **Edit in place.** Each card is editable and saves as you go.
- **Section note.** Under each section: "How should this change?" and **Rewrite**. The note
  is applied as a surgical edit: change only what the note asks for, reproduce everything
  else word for word, keep the section's length and shape unless the note says otherwise
  (BlogForge's `section_revise` rule). With no note, **Write again** writes the section
  fresh from its brief, the sections before it and the sources.
- **Whole-draft note.** One box at the top ("tighten throughout", "more casual"). Each
  written section is revised in order with the whole draft as context, with progress and
  Stop. A section that fails leaves the others done.
- **Selection.** Selecting text shows Rephrase, Shorten, Expand, Fix and Ask…. The result
  replaces the selection.
- **Versions.** Every rewrite, revise, restore and the first save of an editing session
  keep the previous text first. **History** on a section, the title or the opening lists
  versions with a word-by-word comparison and **Restore**. A restore is itself a version.
- **Outline tab.** Rename, reorder, add and remove sections and edit each one's brief.
  **Write the draft** (whole) or **Write this section** works from it.
- **Sources panel.** What the draft used, with **Add a source** at any time; later rewrites
  and the fact check read the new source. "Needs you before publishing" gaps from the
  writer appear here, never in the prose.
- **Top bar.** Copy, Download, Google Doc, Mark as published, and **Finishing**.

One job runs per blog at a time; the desk shows it and offers Stop.

## Finishing

An optional side panel. Every tool proposes, the person previews before and after, then
chooses **Apply**, **Edit** or **Skip**. Nothing changes until Apply, and each Apply keeps
a version first.

- **Humanize** (light, medium, strong): sentences that read as machine-written, each with a
  suggested rewrite. Numbers, names, quotes and links are kept; a suggestion that would
  change a fact is flagged.
- **Apply a voice:** pick a voice guide; the draft is rewritten in that voice keeping
  structure, facts and quotes; per-section before and after; apply all, some or none.
- **Proofread:** instant mechanical checks (banned words, dashes, repetition) with no job;
  **Fix** on a finding rewrites only that sentence.
- **Check facts against sources:** each claim marked supported, not in your sources, or
  contradicted, with the passage; fix the wording, add a source, or keep it.
- **Headline and opening:** alternatives to apply.
- **Before publishing:** the existing pre-publish check, Repurpose (each output a new
  draft) and Send to Google Doc as suggestions.

## Voice guides

**Voice guides** replaces the Voices screen. A guide has a name and text. **New voice guide**
takes a name and either 3 to 20 pasted or uploaded samples (**Make the guide**, one job) or
text written by hand; the text stays editable. Existing learned voices appear as guides.
Kinds of post stay where they are, including saving a style from examples.

## Hidden for now

A single switch, off by default, hides: Write as, Default voice, Change the voice, voice
learning and audition, LinkedIn import, links-to-posts voice import, voice samples in
uploads and the library, "Create voices for every author" and author suggestions. The
server refuses those routes while the switch is off and writes new blogs with Tone (no
default voice is applied). Saved voices, samples and the `record['voice']` model stay on
disk untouched so existing runs keep their pins.

## Kept

Kinds of post and their guides, sources and roles, Google Doc intake, the team library as
a place to pick sources and examples, length, the approved-messaging stance, notes kept
out of the prose, the research path for web and sites, the polish, factual-support and
pre-publish checks, repurpose, Google Doc handoff, delete from the list, and the shared
settings.

## Old blogs

Blogs started in the step-by-step flow open in it as today; their code stays. A finished
old blog offers **Open on the desk**, which brings its manuscript in as a desk draft (the
old run stays readable). New blogs always start on the desk.

## Under the hood

- **Desk record.** In each desk blog's folder: `desk/draft.json` (title, opening,
  sections with id, heading, brief and text, sources, gaps) and `desk/versions/<part>.jsonl`
  (last 20 per section, title and opening). `manuscript.md` is rewritten on every save so
  Copy, Download, Google Doc, library keep and pre-publish work unchanged. Splitting is by
  `##` heading; text before the first heading is the opening. Writes take the studio lock
  and carry the version the form last saw; an outdated form is refused.
- **Jobs.** New kinds on the existing single-worker job queue (`tool_jobs`): `desk-angles`,
  `desk-outline`, `desk-draft`, `desk-section`, `desk-revise-all`, `desk-selection`,
  `desk-first-pass`, `finish-humanize`, `finish-voice`, `finish-facts`, `finish-headline`,
  `voice-guide`. Each job's guidance is assembled from the kind of post, length, tone,
  sources with their stance, and the house guide, as runs do today. Section and selection
  jobs send the minimum context (outline, neighbouring text, the section) so they finish in
  seconds to under a minute; a whole draft takes minutes. Research, when asked for, runs
  before the draft without stops.
- **Proofread** runs in process (text checks), no assistant.
- **Finishing** results are proposals stored beside the draft until applied; applying is a
  text swap that keeps a version.
- **Page.** A new plain script, `desk.js`, beside `runner.js`; `index.html` loads both.
  The start screens move to the new flow; the gate screens stay for old runs.
- **Switch.** `features.voice` in Blog Studio settings, read by the page and enforced by
  the server.

## Delivery

Five pull requests, each usable on its own:

1. The desk with **A draft (edit)**: desk record, versions, section and whole-draft notes,
   selection actions, History, the first pass, Open on the desk for finished old blogs.
2. Author and co-author: the new start screens, angles, outline tab, draft and progress.
3. Finishing.
4. Voice guides and the switch.
5. Docs, command reference and cleanup of unused start-screen paths.

## Testing

Disposable settings, workspaces and a fake assistant; no provider jobs and nothing in the
owner's studio. Covered: splitting and joining a draft, version cap and restore, a stale
form refused, the surgical section rule (text outside the note's scope unchanged in the
fake's output check), each job kind's guidance, one job per blog, Finishing preview then
apply with a version kept, proofread findings, voice routes refused while the switch is
off and new blogs written with Tone, old runs opening unchanged, Open on the desk. Page
journeys in `check-management.cjs`: each start, the desk note and History, selection
actions, Finishing preview and apply. The full Blog Studio suite before each merge.

## Out of scope

Presentation Studio and Training Studio; real-time token streaming; chat with the draft;
removing voice code from the repository.
