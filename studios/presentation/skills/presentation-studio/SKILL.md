---
name: presentation-studio
description: Create, inspect and revise branded slide materials on the Presentation Studio desk in conversation, using checked Harness Slides and Harness Research submissions. Resume supported saved decks without losing their decisions or originals.
---

# Presentation Studio

Use the checked `studio desk` commands for conversation work. They use the same desk without a browser or another assistant. Focused requests never imply drawing, delivery, approval or design answers. `studio serve` still opens the page.

## Rules

- **Only the person approves.** Checked submissions record inputs and provenance, never approval or Ready.
- **Slides use Harness Slides.** Its contracts, compile, preview, patch, comparison and brand checks still apply. Never write slide files directly or invent checked drawings or research.
- **Respect requested scope.** Require an explicit finite material list derived from the person's request. Add or remove scope only after they explicitly ask; never widen to make a submission pass.
- **Design answers are the person's.** Never choose a look or fill design answers from permission to draft. Preserve a saved choice; pass on a companion's request for missing answers.
- **Keep originals.** An existing deck is read and its result is a new file. Preserve sources, pins, History, Google baselines and team ownership.

## Start or continue

1. Read shared defaults from `~/.config/studios-config.json`, or `STUDIOS_CONFIG`: workspace, person, brand/variant and output. Do not write shared settings from conversation. An unconfigured workspace needs explicit setup first; never install or update anything automatically.
2. Follow [the routes](references/routes.md). Prepare the normal checked form, plus `scope`, then `studio desk create --input FILE` (or `--input -` for stdin). Creation returns the folder, checks no assistant readiness and starts no jobs. Uploads are explicit; Google is never fetched silently.
3. For a saved desk, inspect `studio desk show --folder PATH`. To continue its work in chat at the person's request, read `studio desk context --folder PATH --target ownership`, then `studio desk take --folder PATH --input FILE` with that basis and explicit scope. It changes ownership only. Gated decks keep their [saved path](references/workspace.md).

## Work in this conversation

Read `studio desk context --folder PATH --target TARGET`. It returns pinned inputs, current scope, validation requirements and `expected_basis`, including for absent materials. Supply content through `studio desk submit --folder PATH --input FILE`; `desk save` accepts the same envelope:

```json
{"kind":"outline","target":"outline","expected_basis":"<returned basis>","payload":{"outline":{}}}
```

[The desk contract](references/desk.md) lists targets and payloads. Follow returned requirements; never hand-edit run records. Read context again after changed inputs. Refusals preserve canonical work.

For a later explicit change in requested work, read target `scope`, then `desk scope` with `{expected_basis, scope}`. For explicit runner execution, read target `handoff`, then use `desk handoff` with the same fields. Incompatible scope is refused; finish focused work in conversation.

See [research](references/research.md), [existing-deck levels](references/levels.md) and [workspace records](references/workspace.md).
