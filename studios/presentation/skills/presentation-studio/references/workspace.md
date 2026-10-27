# The workspace

Decks live in a `presentations/` folder: in the team's shared repository, beside Training Studio's `trainings/` and Blog Studio's `blogs/`, or in a folder on this computer. `presentations/hub.json` says `{"schema": 1, "tool": "presentation-studio"}`. If there is no such folder, ask where decks are kept before making one. The team repository is `team.repository` in the shared values.

## A deck's folder

`presentations/<deck-id>/`, the id being the title in lower case with hyphens, numbered when that is taken.

```
README.md          title, route, where it stands, the delivered link
run.json           the run record; what marks the folder as a deck
intake.md          the form, in words
classify.md        a document's kind, or an existing deck's inventory
research/plan.md   research/report.md
outline.json       the outline as harness-slides reads it
outline.md         each slide's title, key message and notes
look.md            the brand the deck is made in, and its looks
brand/             brand-contract.json, DESIGN.md, VOICE.md
reviews/build-<n>.md    what the review of each round of the build found
desk/              a desk deck's kept versions of each slide's words
deliver.json       the Google Slides link or the .pptx name, and the revision
contact-sheet.png  one small picture of the deck
sources/           never shared: documents and the original deck
work/              never shared: harness-slides' workspace, the build plan and what
                   each section drew (work/build/), previews and renders
```

## run.json

Write it in the runner's shape:

- `schema` 1, or 2 when `review_policy` is not Step by step (3 is the runner's, for research it started under a research contract), `id`, `title`, `route`, and `form`: `route`, `title`, `audience`, `goal`, `minutes`, `brand`, `variant`, `output`, `research`; for an existing deck also `level`, and `selected` for that level.
- `classified`: `"spec"` or `"material"` for a document, once decided; else `null`. `look`: `null`.
- `steps`: each step finished, as `{"done": true, "at": "<time>"}`, by the runner's names, in order: `intake-source`, `classify` (document), `inventory` (existing), `research-plan`, `research`, `research-report`, `extract` (existing, not `selected`), `outline`, `brand`, `look-preview`, `patch` (`selected`), `build-start`, `build-sections`, `build-whole`, `build-review`, `build-repair`, `build-render`, `deliver`. Only those the route and level have.
- `gates`: each stop, `gate:classify`, `gate:research-plan`, `gate:research`, `gate:outline`, `gate:look` (the look) or `gate:build`, as `{"state": "approved"}`, or `"changes"` with the person's `note`, with `at`, and `by` from `person.name`.
- `review_policy`: `{"schema": 1, "level": "step_by_step"}`, or `balanced` or `automatic`: the level the person chose, kept when the runner brings the deck in. Without it the deck is read as Step by step.
- `revisions` `[]`, and `driver`, `halted` as `null`.
- `flow` `"desk"`, with `desk` and `opened_on_desk`, mark a [desk](desk.md) deck: the runner's alone.

The runner carries on at the first step not done or stop not approved. Work kept in `sources/` and `work/` is not shared, so it redoes a step whose work it lacks.

## What is never shared

`*/sources/`, `*/work/`, lock files, and the guidance caches harness-research and harness-slides keep. `presentations/.gitignore` lists them; keep it so.

## With a team

- **One computer drives a deck at a time.** A deck whose `run.json` names a driver other than this computer is someone else's: read it, do not change it.
- **Each decision is a commit**, saying what was decided. Share it when the person asks, or after each decision when `share` in the shared values is `decision`. Never force a push. If the shared version moved on, stop and say so.
- **The runner** can bring a deck made here into its workspace and carry on from its `run.json`. A deck the runner drives is never also driven from a conversation.
