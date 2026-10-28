# Work in this conversation

Use `studio desk` from the installed Training Studio runner, with JSON files or `--input -` for stdin. A configured workspace is required. Creation checks no assistant readiness and starts nothing. Never install automatically or edit bookkeeping.

## Create exactly the requested work

`studio desk create --input FILE` takes title, topic, audience, purpose, levels (`[]` or 101/201/301/401), materials (`document`, `brief`, `scenario`), brief_kind, deck_target, brand, research_from and required scope. Scope is a finite list from `text`, `outline`, `research`, `drawing`, `part`. Derive it from the person's actual request; never add research or drawings to an outline request. For only a teaching plan, use `materials: []`, no deck_target, and `scope: ["outline"]`. The plan may record that research was not supplied; it stays Draft. Supplying research later holds it for a checked update.

Copies and Yoodli are off unless explicitly requested. Google links are not fetched. Explicit local uploads map a filename to an absolute path; select documents in research_from first. Original uploads and source scope are pinned.

## Context and checked submissions

Run `studio desk show --folder PATH`, then `studio desk context --folder PATH --target TARGET`. Context returns `{target, expected_basis, scope, inputs, requirements}` even before a material exists. It includes pinned source text. Follow the returned checks and templates.

Submit `{kind, target, expected_basis, payload}` with `studio desk submit --folder PATH --input FILE`. `desk save` is the same checked operation. Use the returned basis; changed inputs refuse. Keep operational metadata out of prose.

| Kind | Target | Payload |
| --- | --- | --- |
| text | research-plan | `{plan}` with the returned source scope and sources |
| research | research | `{case}`: absolute local complete, independently reviewed Harness Research case |
| outline | blueprint, blueprint@101 | `{text}`: checked teaching plan |
| outline | deck-outline, deck-outline@101 | `{outline}`: complete checked slide outline; design when requirements request it |
| text | document, brief, scenario:ID, yoodli:ID | `{text}`: checked complete material |
| drawing | deck, deck@101 | `{sections}`: exactly the requested IDs and checked compositions |
| part | document/PART or deck@101/SLIDE/FIELD | `{text}`: current editable part or stable slide/field |

Apply the same @level to every level-specific target. Scenario IDs come from the practice plan; arbitrary names and paths refuse. Sources sections are maintained from citations. Existing part edits use the desk revision and preserve History; they do not clear holds. Initial materials use the normal material checkers and save operations. Acceptance is continuation, never the person's approval or Ready. Drawings compile, preview and receive the brand audit; absent reviews stay absent. Google-target edits keep a separate local PowerPoint draft and preserve the delivered link, baseline and earlier approval. It stays Draft and cannot be marked Ready until explicit delivery. Missing local drafts refuse safely. No copies or delivery follow a submission.

## Ownership and scope

At the person's explicit request, read target `ownership` then use `desk take` with `{expected_basis, scope}`. Retain existing scope, or supply it for an older desk. This changes execution metadata only; materials, practice metadata, History, Google baselines and approvals stay. Gated saved work retains its saved path.

For a later explicit broader or narrower request, read target `scope`, then use `desk scope` with `{expected_basis, scope}`. Never widen on submission. Explicit `desk handoff` uses target `handoff` and the same fields; it checks the actual remaining runner plan, pinned runtime, current scope and readiness before transferring execution. Copies, Google delivery or incompatible scope refuse. A page visit, restart or recovery never transfers chat-owned work.
