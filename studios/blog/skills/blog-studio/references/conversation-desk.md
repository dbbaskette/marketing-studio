# Blog Studio work in conversation

Requires Blog Studio 4.8.0 or newer. Use the current conversation to write the
requested material. Do not open a browser, run another assistant, install or
update a companion, or schedule a worker merely to draft or save work.
`...` below means `<python> <runtime>/studio.py --root <absolute-workspace>`.
Use `... init` only after an explicit setup or launch request for a new workspace.

## Create and inspect

Save a bounded JSON object outside the installed skill, then run:

```sh
... desk create --input request.json
... desk show --article ID
... desk context --article ID --target outline
```

Every `--input` also accepts `-` for JSON on stdin. Commands print JSON and refuse
unreadable, oversized or conflicting requests. Keep the returned article ID.

Creation takes the same fields as the desk: `title`, `way`, `point`, `audience`,
`outline`, `outline_source`, `manuscript`, `source`, `article`, `style`, `tone`,
`length`, `sources`, `library` and `research_from`, plus `author`, `brand`,
`variant` and conversation `scope`. Choose only the sources the person selected.
Sources use the desk's source selections and library roles, never arbitrary paths.
Existing imported articles retain their original, source and voice pins.

- A supplied draft uses `manuscript` (Markdown), `source` (a saved source ID), or
  `article` (an already imported article ID), one only; `way` defaults to `draft`.
- A topic uses `way: "topic"`, `title` and `point`, with optional `audience`.
- Supplied outline or interview notes use `way: "outline"` or `way: "shape"`
  and `outline` text or a saved `outline_source` ID. Shape stops at the outline.
- `scope` is `draft` by default, `outline` for an outline-only request or
  interview, `research` for research-only work, or `part` for editing a supplied
  draft. Outline and research scopes require a topic or notes. Do not broaden a
  focused request to a whole draft or research pipeline. Ideas and interview
  questions may remain in conversation until there is a brief worth saving.

Creation pins the saved author and brand defaults. Explicit `author` and `brand`
choices win; an empty string opts out. Use `variant` only with a brand. New desk
writing uses `tone` only, without a default author voice. A saved article's
explicit voice pin is preserved. An explicitly requested voice transformation
uses the separate voice tool. Brand naming rules stay separate from author voice.

## Checked submissions

Context returns `{target, expected_basis, scope, inputs, requirements}`. Read its
pinned inputs and requirements before writing. A missing draft, outline or research
result still has a basis. Submit the exact envelope below with `... desk submit
--article ID --input result.json`:

```json
{"kind":"part","target":"opening","expected_basis":"VALUE_FROM_CONTEXT","payload":{"text":"REQUESTED_TEXT"}}
```

| Kind | Target | Payload |
| --- | --- | --- |
| `text` | `draft` | `content`: Markdown, up to 200,000 characters; optional `notes` and `gaps` kept outside the writing |
| `outline` | `outline` | `title`, `opening_brief`, `sections`: rows with `heading` and `brief`; initial outline only, with no existing prose or part History |
| `part` | `title`, `opening` or an existing section ID | `text`, checked for the part's shape |
| `research` | `research` | `case`: absolute local Harness Research case directory containing its complete independently reviewed `research/` bundle |

Kinds and targets must match. Clearing prose does not reset existing work to an
initial outline; use `desk outline-save` to retain its sections and History. Research uses the existing bundle checker; raw
assistant-written research is refused. Use the existing Harness Research contract
when the person requested research, then submit its checked output. Source IDs,
editorial notes and publishing gaps stay outside reader-facing prose. Examples
show shape and style; their facts need independent support from selected sources.
Accepted submissions keep a bounded provenance receipt for the inputs read and the
requested target. A context/submission pair grants no approval, publication or delivery permission.

For typing or an existing part edit, `... desk save --article ID --input edit.json`
takes `{"seen":1,"part":"opening","text":"REQUESTED_TEXT"}` using the revision from
show. History retains the replaced text. A same-part change refuses the old save;
a different unchanged part may still save. A basis-bound submission refuses any
changed input, worker or team ownership; read context again and reconcile.

## Edit an existing outline

Read `... desk context --article ID --target outline`, then use
`... desk outline-save --article ID --input outline-edit.json` (or `--input -`).
The JSON is `{"expected_basis":"VALUE_FROM_CONTEXT","rows":[{"id":"SECTION_ID",
"heading":"REQUESTED_HEADING","brief":"REQUESTED_BRIEF"}]}`. Supply the complete
ordered list: existing rows keep their returned IDs, new rows omit `id`, and a
current row omitted from the list is removed only when the person requested it.
Reorder rows to change order. Text and History follow existing IDs. Removed rows
and their History remain readable in `desk show` and are retained for recovery. Changed inputs, an active worker or another driver
refuse the save. The operation starts no work and grants no approval.

## Explicit scope change

Only after the person explicitly asks to broaden or change the work, read context
for its current scope target (`draft`, `outline`, `research`, or `opening` for
`part`). Then use `... desk scope --article ID --input scope.json` with
`{"expected_basis":"VALUE_FROM_CONTEXT","scope":"draft"}` (or another listed scope).
This keeps the same article and records the explicit change. It preserves material
bytes and History, starts no work and grants no approval. Old context refuses after
a scope change; read fresh context for the newly requested target, then submit it.
A worker or another driver prevents the change. Do not use this command to turn an
outline, interview, research or passage request into a draft without being asked.

## Explicit runner handoff

Conversation creation, reads and saves never wake automatic work. Visiting the
page does not transfer ownership. The person may explicitly invoke a narrow page
tool; its existing version, team and worker checks still apply. Automatic begin,
retry and continuation remain blocked for conversation work.

Only when the person asks the runner to continue, read context for the current
remaining step (`research`, `outline` or `draft`), then run:

```sh
... desk handoff --article ID --input handoff.json
```

The input is `{"expected_basis":"VALUE_FROM_CONTEXT","scope":["outline","draft"]}`.
Scope lists only requested remaining steps, in their saved order. The handoff
rechecks inputs and ownership under the write lock before transferring execution
and queuing the first requested step. It never publishes or approves anything.
A narrower earlier request does not authorize drafting or outside research. If a
changed scope has no compatible remaining saved plan, handoff refuses clearly;
continue with checked submissions in the same conversation.

## Proofread, Finishing and saved work

Proofread's Quick check now includes source IDs, editorial notes and example
carry-over alongside mechanical checks. GEO in Finishing explicitly proposes
retrieval-readiness changes. Preview each proposal and apply or skip it; applying
keeps History and refuses changes that no longer fit. These checks never establish
live source acceptance or authorship.

Older step-by-step records retain their [saved-work commands](guided-runs.md),
source pins and decisions. `run create` now explains how to create desk work.
Do not duplicate, silently migrate, or mark unfinished work Ready.
