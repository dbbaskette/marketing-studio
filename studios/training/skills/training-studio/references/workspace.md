# Workspace

The helper's `save`, `checkpoint` and `export` below work on a desk training this computer runs. Desk work in a conversation uses the [conversation commands](conversation.md) instead.

Deliverables are files in the training directory. Bookkeeping is under `.training-studio/`.

## Artifacts

| Artifact | File | Built from |
| --- | --- | --- |
| `intake` | `intake.md` | nothing |
| `research-plan` | `.training-studio/research-plan.json` | `intake` |
| `research` | `.harness-research/research-report.md`; copied to `research-report.md` on approval | `research-plan` |
| `blueprint` | `blueprint.md` | `intake`, `research` |
| `document` | `document.md` | `blueprint` |
| `brief` | `product-brief.md` or `competitive-brief.md` | `blueprint`, `research`, the brief kind |
| `deck` | `deck.pptx`, or `deck-link.md` for Google Slides | `blueprint`, `document`, the deck target and brand |
| `scenario:<id>` | `scenario.md` (the ID is `main`) or `scenarios/<id>.md` | nothing; the user owns it |
| `yoodli:<id>`, only if Yoodli is on | `yoodli/<id>.md` | `blueprint`, `brief`, `scenario:<id>`, the Yoodli profile |

## Status

| Status | Meaning |
| --- | --- |
| `not-started` | The file does not exist |
| `draft` | Not approved in its current form |
| `approved` | The content and what it was built from are what the user approved |
| `stale` | Something it was built from has changed, or is itself stale |
| `skipped`, `unavailable` | Its stage was skipped, or could not run |

Status is computed from the files each time. Changing a setting makes only the artifacts that use it stale.

## Saving

| Command | Use |
| --- | --- |
| `training.py save <artifact> --built` | A first version, or a file another tool wrote in place |
| `training.py save <artifact> --from <file>` | A rebuilt version, written first to a scratch file outside the directory. The version it replaces is kept |
| `training.py save <artifact>` | A hand edit. It never claims a rebuild and never clears staleness |

Never use `--built` or `--from` to clear a stale flag. A save is never the person's approval: a material is Ready only when they mark it so on the desk.

A saved record is not continued here: if `training.py status` or the page says the training is one, use Bring it in, Open on the desk or Start new work from this, as its page offers.

## Copies

`settings.copies` in `status` is what the user chose: `google`, `word`, both or neither. Change it with `training.py checkpoint --copies google word`; `--copies` alone is none. Each wanted copy is `current`, `outdated`, `missing` or, for Word, `unavailable`.

- **Google Docs.** `google_docs` lists each document and brief. `training.py google push <artifact>` makes or updates one; see the google reference.
- **Word.** `exports` lists each artifact that needs a `.docx` beside its source. `training.py export <artifact>` makes it with pandoc and records it. If it answers `unavailable`, tell the user why. A copy made another way is recorded with `--file <path>`.
- **With Yoodli on,** the user uploads the brief's copy: its Google Doc when `google` is kept, otherwise a Word copy, which `exports` then lists with each `yoodli:<id>` whatever was chosen. Without one, tell the user the Yoodli handoff is incomplete. If a Google Doc cannot be made, ask whether to drop `google`.

Redo a copy after every change to its source. Never tell the user to share or upload one that is not `current`.

## History and other rules

- Earlier versions are in `.training-studio/history/`, in a folder named for the artifact with `:` and `@` written as `-` (`scenario-main-101`), each file named by its SHA-256. `events` in `session.json` gives the order. Restore one with `training.py save <artifact> --from <that file>`.
- A refusal is `{"error": ...}` with exit code 2. Show it to the user as it is. Run one command at a time.
- The helper never commits to git. Commit only when the user asks.
