# Profile storage

Use the [workspace](../workspace.md) command prefix. Create the guide/audition
with the harness before saving it. [Voice setup](../voice-flow.md) covers sample
selection and LinkedIn extraction; imports do not create profiles automatically.

```text
... profile create --name <author> --guide-file <guide> --background-file <bio> --rules-file <rules> --sample <source-id>
... profile save --id <profile-id> --guide-file <revised-guide> --status confirmed
... profile show --id <profile-id> --revision <number>
... article voice --id <article-id> --profile <profile-id> --revision <number>
```

Supply optional background/rules/samples only when present. Samples must be
ready and explicitly classed as authored voice-sample. Rules JSON accepts
`banished_words`, `banished_phrases` lists and `no_em_dashes`,
`no_ascii_double_hyphen` booleans: use the author's choices, not universal bans.

Revisions retain guide, biography, rules, samples, and confirmation state.
Report provisional profiles honestly. Read the article's pinned revision;
saving a new profile does not switch existing articles. Switch only deliberately;
affected reviews become stale. Return profile ID/revision/status and material
changes rather than the full sample library.
