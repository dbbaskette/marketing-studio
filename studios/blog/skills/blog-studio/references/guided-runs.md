# Saved step-by-step Blog Studio work

Blogs saved with `derived/blog-run.json` by the earlier step-by-step flow are saved
records. That flow continues none of them: no stage of theirs is written, submitted,
approved or changed, in chat or on the page, and the commands that did so are gone.
Only the manuscript editor's own review and revise runs (a run with `editor_check`)
still go on, from **Edit manuscript** on the page. New work uses
[conversation desk commands](conversation-desk.md); `run create` refuses with those
commands.

`...` means `<python> <runtime>/studio.py --root <absolute-workspace>`.

`... run list` lists saved blogs and `... run status --id <id>` reads one: its pins,
stages, decisions and what its last step said. Reading changes nothing. Never write a
run record by hand, copy one or start one again.

## What becomes of each one

The page shows each saved blog as a saved record with one main action, by the same
classification the migration preview gives (`outcome`, `reason`):

- **Opens on the desk**: it saved an outline, a draft, a review or a handoff. Only
  when the person asks, use the preview and guarded
  [unfinished-work migration](desk-migration.md); it keeps every original byte.
- **Finished**: its Done card works as before: its own Open on the desk, copy and
  download, a private Google Doc, pre-publish checks, repurposing, Mark as published,
  Delete, and Polish or edit the draft in the manuscript editor.
- **Read-only**: it stopped before an outline or draft (angles, research, a claims map,
  a brief only), or its records cannot be read or understood. Its saved files are read
  in place. **Start new work from this** opens a desk start with its title, point and
  audience; nothing it researched or made is carried over.
- **Waiting** (only a blog that would open on the desk): a step running now (Stop it),
  another computer driving it or an identity to record (Take it), a tool task waiting
  for the person (open it where it is finished), an interrupted opening (Finish opening
  on the desk), or a workspace or computer condition the record names and says how to
  clear, with new work from it meanwhile. A marker the earlier flow left that no runner
  picks up again keeps nothing waiting.

## Manuscript editing on the page

**Edit manuscript** supports local Markdown edits, scoped checks, selected findings,
and explicit Google suggestions/comments delivery. Opening a Google Doc goes there
after preview. Preserve the original author voice; selected replacements can be
applied locally before delivery. Each send is previewed and revision-checked through
the same Google review helpers as the CLI. Conflicts remain local until reconciled.
A check runs as the editor's own review or revise run: it stops after each step for
the editor, which reads its findings; a finished one reads on its run and gate screens.
The check refuses an unfinished saved run it did not make: that blog opens on the desk.
