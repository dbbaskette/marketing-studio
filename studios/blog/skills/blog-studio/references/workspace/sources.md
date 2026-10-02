# Source storage

Use the [workspace](../workspace.md) command prefix after host extraction.

```text
... source add --name <name> --file <original> --text-file <readable-md> --origin <url-or-file> --purpose reference
... source add --name <name> --origin <url> --purpose reference --status unavailable --note <reason>
... source show --id <source-id>
... source update --id <source-id> --text-file <updated-md> --status ready
... article attach --id <article-id> --source <source-id> --purpose reference
```

Raw bytes and prior revisions remain available. Markdown/text may supply their
own readable text; binary originals need extraction or stay pending. Ready means
nonempty content was actually read. Preserve provenance and access limitations.
Repeat `--purpose` for multiple roles: manuscript, outline, reference, inspiration,
voice-sample, author-background. Article roles may differ from library roles.

Attach only selected material. Source changes do not silently refresh an
article's chosen context; inspect changed-since-attach and review freshness.
Use recorded revisions/passages for claims, not an automatically newer summary.
Return source ID, roles, readiness, and gaps; read bodies only for the task.
