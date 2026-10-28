# The three routes

Keep the person's exact requested scope. The form uses `route`, `title`, `audience`, `goal`, `minutes`, `brand`, `variant`, `output` (`google` or `pptx`), optional brief `notes`, and required finite `scope`. Creation starts no worker. An outline request adds no research or drawings.

| Starting point | Checked form and inputs |
| --- | --- |
| An idea | `route: scratch`; brief and optional explicitly enabled research |
| A document | `route: document`; `source` names an upload, pasted text or Google link; `reading: spec` or `material` when the person chose it |
| An existing deck | `route: existing`; preserved input deck and one of the five [levels](levels.md); Selected changes also requires `selected` |

For uploads, name `source: {kind: upload, name: NAME}` and explicitly supply that name's local file through CLI `uploads` or API bytes. Pasted documents use `{kind: paste, text: TEXT}`. Google input never triggers a silent read, authentication or delivery. Originals remain intact.

## Focused writing and research

Read target context; submit against its basis. An outline-only supplied document works without extra requested text steps when its reading is already explicit. Otherwise the missing classification is a genuine prerequisite: ask the person and explicitly change scope if they request that work. A supplied existing deck is inventoried locally through Harness Slides; its level still constrains every word and slide that may change.

Research requires both the form's explicit research choice and the submitted kind in current scope. Follow [the research handoff](research.md), within pinned document/site/web permissions. Import a complete reviewed case through target `research`; never save unsupported prose as evidence. The outline receives its brief, source relationships, conditions and gaps. A plan is not permission to execute it.

## Drawing and revisions

Target `drawing` returns exact section composition requirements from the checked outline and brand contract. The current conversation supplies compositions; existing compile, native preview, fixed-word and brand checks validate them. No nested assistant draws them. A saved picked look is preserved; using the brand default at creation requires the person's explicit choice. Missing design answers are refused and never filled automatically.

Part edits use stable slide IDs and known fields. They preserve unchanged sections, check fit, keep History, and update the native file without a composer. A changed outline retains unaffected sections; a changed delivered deck keeps prior delivery decisions and revisions as history, with the new revision unapproved.

To broaden/narrow the same desk after the person asks, use checked `desk scope`. To continue an idle saved desk in chat, use checked `desk take`; neither starts work or changes readiness. Explicit `desk handoff` checks that the remaining runner plan fits current scope and pinned inputs. It may refuse a narrow scope; focused work can finish in conversation.

Older gated records keep their saved readers and decisions; use [saved work](workspace.md).
