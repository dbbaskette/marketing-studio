# Explicitly open unfinished saved work on the desk

Requires Blog Studio 4.9.0 or newer. `...` means `<python> <runtime>/studio.py --root <absolute-workspace>`.

Only when the person asks to move saved work onto the writing desk:

```sh
... desk migration-preview --article ID
... desk migrate --article ID --expected TOKEN_FROM_PREVIEW
```

Read the preview's retained materials, incomplete work and blockers first. Its
`expected` is an opaque machine value; pass it unchanged and do not display it.
The page's **Open on the desk** offers the same preview, Cancel and guarded apply.
Cancel changes nothing. Apply keeps the same blog and starts no worker, research,
approval, publication or delivery. Execution belongs to the conversation; opening
the page does not hand it to the runner. Finished blogs keep their existing action.
An outline-only saved request keeps outline scope; a manuscript review without a
drafting step keeps part-edit scope. Moving it does not authorize a broader draft.

Eligible work has readable `DRAFT.md`, `ORIGINAL.md` or `OUTLINE.md`. An outline
of two or more heading sections that round-trips becomes briefs with empty prose;
other outline notes are kept whole as the start's notes, outline step still to do
(notes holding image data refuse). Limits: 200,000 characters and 60 sections,
4,000-character briefs, desk image limits, 2,000 files and 32 MiB checked, 1 MB
records.

This covers waiting or finished outlines and ideas, a waiting draft, review or
handoff, an author's outline, a supplied manuscript's review or revision, runs
continued without research or saved with a research execution record, paused,
stopped or failed page runs (nothing is retried) and editor reviews.

Brief-only starts, early research or angles without materials, missing documents
or pins, unreadable or unsupported records, links, active jobs, older Team Hub
contexts and oversized work refuse; the saved flow stays. A blog with no run
refuses; Edit manuscript brings its draft to the desk. Research, reviews and
handoff stay historical; gaps stay unresolved. On the page, an unreadable saved
blog is a read-only record: why, its files, and Start new work from this.

Unknown worker formats, statuses or ownership refuse, even when disabled. Stop known
work and wait for its process to end before previewing again; never edit records to
bypass refusal.

Migration leaves original `session.json` and `derived/blog-run.json` bytes in place,
including after later checked desk saves. Separate fixed desk metadata holds the
live desk session and preserves the original progress and real versus automatic
approval facts. Material, History, source/voice/guidance pins, Google baselines and
team driver records are retained. Read context again after opening on the desk.

Later source pins, Google links and publication decisions use the live desk session.
Unreadable records block source changes, input deletion and linked Doc writes until
restored.

A changed source, record, file, driver or worker refuses the old preview. Inspect
and preview again; never replace a pin or approve a step just to make it fit.
Migration saves locally; sharing remains the existing explicit team operation.

If a process stops during apply, its pending record excludes workers, recovery
cleanup and synchronization replay. Repeat the original `desk migrate` command
with the same preview token: under the write lock it removes only unchanged
outputs from that interrupted attempt, checks the original preview again and
applies. If inputs changed it safely refuses after rollback; preview again.
If an output or journal was altered or is unreadable, restore the retained desk
records before retrying; do not delete markers, edit approvals or resume a worker
to bypass the refusal. No original writing or run records are rolled back.
