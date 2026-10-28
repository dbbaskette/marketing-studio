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

Eligible unfinished work has readable supported `DRAFT.md` or `ORIGINAL.md`, or
a Markdown `OUTLINE.md` with at least two heading sections whose complete text can
round-trip through the desk without loss. Outline text becomes briefs, with empty
prose and drafting still incomplete. Manuscripts are limited to 200,000 text
characters and 60 sections; outline briefs to 4,000 characters each. Images retain
the existing desk limits. The checked local scope is bounded to 2,000 files and
32 MiB; original session/run and desk interpretation are each at most 1 MB.

Brief-only starts, early research or unchosen angles without usable materials,
unstructured/list outlines, missing declared documents or pins, unreadable or
unsupported records, links, active or unsettled jobs, older Team Hub contexts and
oversized work refuse with the saved flow still available. Research, reviews and
handoff stay as historical records; gaps remain unresolved. These early formats
retain their saved-flow commands until a supported lossless transform is proven.

Migration leaves original `session.json` and `derived/blog-run.json` bytes in place,
including after later checked desk saves. Separate fixed desk metadata holds the
live desk session and preserves the original progress and real versus automatic
approval facts. Material, History, source/voice/guidance pins, Google baselines and
team driver records are retained. Read context again after opening on the desk.

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
