# Later explicit requests

Changing the finite kind scope alone preserves all native material selections. To add or remove requested materials on the same desk after the person explicitly asks, read context for `scope`, then use `studio desk scope --folder PATH --input FILE`:

```json
{"expected_basis":"<current basis>","scope":["outline","text","part"],"materials":["document"]}
```

Optional selection fields are `materials` (a list from document/brief/scenario), `deck_target` (pptx/google/null), `brand` (explicit brand/variant object or null), and `yoodli` (boolean). Omitted fields preserve current values exactly. No defaults broaden the work. Copies, levels and delivery are not selection fields. Yoodli still needs brief and scenario.

An outline-only training may later gain a guide with the envelope above, or a local deck with explicit `deck_target: "pptx"`, brand and drawing/outline scope. Then use ordinary context, checked submissions and actual design answers. Adding research also requires research/text scope; a provisional teaching plan is held when new research arrives and needs a checked update.

Selection changes create no material, job, approval or Ready state. Deselected files and History stay. Input settings can hold their dependents. Existing saved decks refuse target or brand conversion; their original link, local pending draft and Google baseline cannot be rebound by a scope change. Metadata-only scope changes preserve the session and all content exactly. `take` and `handoff` keep the original two-field basis/scope envelope.
