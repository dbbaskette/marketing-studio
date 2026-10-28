# The Presentation Studio desk

A desk record has `flow: desk`. Conversation and the page use these records and History. New conversation work also has `execution: conversation`; page visits, restarts, recovery and queued continuations cannot start its workers. The person's explicit handoff transfers execution.

## Checked conversation commands

All commands return JSON. `--input FILE` accepts JSON; `--input -` reads stdin. `create` takes the normal form plus a required `scope` list. Scope contains only `text`, `outline`, `research`, `drawing`, `part`, normalized without duplicates. It permits kinds; target, prerequisites and current basis constrain each operation.

| Kind | Target | Payload |
| --- | --- | --- |
| text | brief | `{text}`: the checked form brief, at most 4,000 characters |
| text | classification | `{classification: {kind, reason, slides}}`: a document's checked spec/material verdict |
| text | research-plan | `{plan}`: checked planning questions within the pinned source scope |
| outline | outline | `{outline}`: complete Harness Slides outline JSON, with original-deck level constraints |
| research | research | `{case}`: absolute local complete, independently reviewed Harness Research case |
| drawing | drawing | `{sections}`: composition objects by exactly the section IDs returned by context; Selected changes uses `{patch}` |
| part | SLIDE/FIELD | `{text}`: current stable slide ID plus a known field |

Fields are `title`, `subtitle`, `detail`, `caveat`, `source`, `notes`, or `points:INDEX:label` / `points:INDEX:text` (zero-based index). Selected changes uses `slide-N/object:ID:RUN`, with `all` for a single run; the existing deck's notes stay unchanged.

`studio desk context --folder PATH --target TARGET` returns `{target, expected_basis, scope, inputs, requirements}`. Submit `{kind, target, expected_basis, payload}` using `desk submit` or `desk save`. Context describes absent materials too. It prepares companion contracts on disposable copies without changing the desk. Checkers run outside the repository lock; current inputs, team ownership and workers are checked again before saving. No arbitrary destination paths are accepted.

`desk show --folder PATH` exposes materials, native drawing state, sources, prior deliveries and History without recovery or jobs. Missing prerequisites receive a refusal, never implicit scope expansion. Drawing requires a checked outline and an explicitly settled look. Validation never chooses missing design answers or runs an assistant.

## Execution and later scope

At the person's explicit request to continue an existing desk in chat, read target `ownership`, then use `desk take --folder PATH --input FILE` with `{expected_basis, scope}`. Supply scope when the old desk has none; retain an existing scope. Only execution metadata changes: originals, material bytes, History, Google records, approvals and readiness are preserved. Busy workers, pending jobs, another driver and changed inputs refuse the operation. Gated saved work needs its supported saved-work/migration path.

At the person's explicit request to broaden or narrow work, read target `scope`, then use `desk scope` with `{expected_basis, scope}`. This changes scope/provenance only. For explicit runner execution, read target `handoff`, then use `desk handoff` with the same fields and current scope. An incompatible remaining plan is refused without broadening or approving it.

## On the page

The existing desk offers slide/whole-deck notes, checked word and speaker-note edits, History, outline changes, source intake and Finishing proposals. Notes redraw only their requested sections; unchanged sections are retained. Selected changes patches a copy and compares it against the original. Brand only and Polish preserve original words. Finishing proposes before Apply; Deliver remains the person's, showing brand blockers first. A change after delivery starts the next revision and retains prior delivery history.
