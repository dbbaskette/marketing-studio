# Create an article

Use the [workspace](../workspace.md) prefix. Resolve [writing defaults](defaults.md)
for missing intake values; explicit choices win.

```text
... article create --title <title> --mode <mode> --research <policy> --profile <profile-id>
```

Modes/stops: existing → review; first-draft/from-outline → draft;
outline-only/interview → outline; discover → brief. Use `--stop` to reflect an
already requested different outcome. Policies: supplied-only, web-allowed,
unspecified. Use optional `--author <name>` when the author is known; do not infer authorship
from the editor. Without a profile replace `--profile` with `--voice preserve` for an
imported manuscript or `--voice tone --tone <tone>` for new writing.

Save audience, takeaway, required points, format/length, selected material and
research limits in the brief via [articles](articles.md). Attach selected
[sources](sources.md). Standalone voice setup creates no article.

For a bootstrap task, bind its actual task immediately:
`... article guidance --id <id> --task <sync-task>`.
Add `--cached` only for an explicitly chosen stale fallback. Retain returned
runtime and exact source/voice/guidance pins; a new task's latest guidance must
not replace an existing article's pin.

For software-product work, keep the inferred article form and any explicit house-style
exceptions in that brief. Reuse selected team terminology and author voice; do not
add a mandatory style questionnaire. [House style](../style/house.md) supplies defaults.
