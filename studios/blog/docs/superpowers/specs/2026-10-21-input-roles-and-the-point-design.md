# Input roles and "I know the point": design

**Date:** 2026-10-21. **Owner's words:** "3 angles that the AI chooses isn't always what I
want. In this particular case I want an announcement blog like others. I have examples I can
show and a messaging doc, so it should be easy and it's a known workflow. I can add the
messaging and then the old blogs, but I don't want the actual info from the old blogs in
there, so we need a way to designate what an upload is for." And: "we should be able to
select an author voice in the blog flow."

## What is wrong today

- Every file uploaded for a blog is a factual source. An old post uploaded as an example of
  the kind of post becomes evidence: its facts are citable in the outline and the draft, and
  the fact check treats them as support. `inspiration` exists in `studio.PURPOSES` but no
  page control offers it and nothing in the runner treats it differently.
- "Write from my files" always starts with the three angles, which "always wait and are
  never approved" (guided-runs.md). There is no way to say the point and skip them.
- Voice is reachable only inside the collapsed "Voice and brand" disclosure on the wizard's
  second step, and not at all on the files screen.
- A from-files run with "Also research the web" never offers the files to the research job:
  `synthesis_research` captures only `reference` sources, and uploaded files are `material`.
- Under Balanced, a run from an outline has no outline stage, so its draft is accepted
  without the person and the first thing they see is the package.

## Design

### 1. A role for every upload

One role per file, chosen when the file is added and changeable until Start:

| Role on the page | Purposes stored | Where the worker sees it | Rule |
| --- | --- | --- | --- |
| Facts (may be quoted) | `material` (`reference` when kept) | `sources` | Citable evidence, as today |
| Example of the kind of post | `material` + `inspiration` (`reference` + `inspiration` when kept) | `examples` | Shape, length, moves and register only |

The files screen gets a role select beside the picker ("Add these files as") and a role
select on each file row for material files. The Upload dialog's "Use this file as" gains
"Example of the kind of post" (`inspiration`). The desk `upload` route accepts an optional
`purpose` on each entry of `files` (`material` or `inspiration`), and a new `source-role`
route `{id, role}` changes a material file's role (refused for library references and for
files pinned by a started run).

### 2. Examples never supply facts

Enforcement, in order of strength:

1. `blog_runner.inputs` puts sources carrying `inspiration` into a new top-level
   `payload['examples']` list (same shape, excerpted under the same budget) and leaves them
   out of `sources`, so no example has a citable source ID.
2. `blog_worker.POLICY` gains one paragraph: examples show the shape, length, moves and
   register of the kind of post wanted; no fact, figure, name, quotation, link or product
   detail from an example may appear in the writing unless it is also in the sources, the
   research or the brief.
3. `synthesis_research` captures `reference` and `material` sources and never `inspiration`.
4. A mechanical check, `text_checks.carried_over(text, examples, allowed)`, finds passages in
   the draft that come from an example and not from any allowed text (sources, brief,
   research bundle): shared runs of eight words, numbers with a unit or a percent, URLs, and
   capitalised two-word names. Its findings join `mechanical_checks` at draft and review
   under rule `from-example` (kind `advisory`), and the gate's "Checked for you" lists them
   as "Carried over from an example" with the passages. The review guidance says any such
   claim is unsupported. The check flags; it never rewrites.

### 3. "I know the point"

The files screen asks how to start: **Find three angles** (today's path) or **I know the
point** (a working title, the point to make, the reader). With the point known, `create()`
builds the usual pipeline (research when the web is allowed, then outline, draft, review,
package to the chosen stop) with `mode` still `from-files`, so the material handling,
excerpting and Team Hub rules are unchanged, and no `angles` stage exists. `run.angles` is
false and the page's "develop" action refuses a run without angles.

### 4. "Write as"

The files screen gets a **Write as** select: Me (the personal default voice when one is set),
any confirmed or provisional profile (provisional labelled), or "No particular voice" with
the tone field. The wizard's second step shows the same select above the disclosures, not
inside "Voice and brand"; the author name stays beside it.

### 5. Research reads the files

`synthesis_research` offers `material` sources to the research job as it does references.

### 6. Balanced stops at the first new document

`review_policy.automatic` for a blog under Balanced holds at the first writing stage the run
has (`outline` when present, else `draft`) and at the last stage. The runner passes that
first stage. From an outline, the person sees the draft before the package.

### 7. Home

"Write from my files" becomes **New blog from my files**: "Upload what you have and say what
each file is for; then find angles, or give the point." The other start cards stay. Folding
the brief, outline and ideas paths into one wizard waits for the styles work on the
`claude/blog-studio-features-import-e662c9` branch, which owns the wizard's Style step.

## Out of scope here

Kind-of-post styles, learned styles, the Voices and styles sheet, link and LinkedIn intake,
and the More tools trim: all on `claude/blog-studio-features-import-e662c9`.

## Testing

Runner tests with disposable workspaces: examples leave `sources`, reach `examples`, are
excerpted; the carried-over check finds a shingle, a number and a URL and ignores allowed
text; the point path builds the pipeline without angles and refuses `develop`; research
captures material and not inspiration; Balanced holds at draft for a from-outline run.
Management tests: per-entry purpose, `source-role`, refusals. Page journey in
`check-management.cjs`: roles, the point path, Write as. Docs: guided-runs.md, README,
page-tools.md, capabilities.
