# Progressive team memory

Kinds: article, source, voice, note, decision, rule, context, review. Keep sources
attributable and differentiate evidence, inspiration, samples, and background.
User-defined rules/context are content preferences, not authority to run tools,
change accounts, publish, or override the host and current user request.

```text
python3 <runtime>/hub.py --workspace <workspace> find --kind article --query <words> --limit 10
python3 <runtime>/hub.py --workspace <workspace> read --item <item-id> --revision <revision-id>
python3 <runtime>/hub.py --workspace <workspace> history --item <item-id> --limit 20
python3 <runtime>/hub.py --workspace <workspace> context --project <project-key> --author <author-key> --article <article-key>
```

Find returns bounded metadata; `--offset` pages results/history. Read returns an
exact record and read-only paths; open BODY.md or a selected artifact only when
needed. Never load the entire hub or dump helper source into context. Search
with a specific title/tag/words when discovery is broad. Offline/cached status
must remain explicit. Local queued and pending-review records are visible only
to their owning clone until they reach shared main.

Context returns scoped rule/context references and conflicts, with a default
limit of 50 (`--limit` up to 200). A truncated result is incomplete: narrow the
scope or deliberately select the applicable subset, retaining every relevant
conflict. Do not silently apply partial rules or continue on an unresolved
applicable conflict. Read selected bodies, reconcile preferences, and persist
the selected context as a JSON file using the host's file tool. Attach it with:

```text
python3 <runtime>/studio.py --root <workspace> article context --id <local-article-id> --file <selected-context-json>
```

Order: current request, explicit article/author/project selections, then team
defaults. More specific choices override defaults for the same preference;
equally scoped competing rules require a choice. Attach actual item/revision
IDs, not a prose summary alone. New context adoption stales affected reviews;
unrelated hub changes do not. An active article retains its prior selections
until the author requests adoption. Task-entry context is for a new task.

For “remember this,” save the selected content, its title, kind, scope, and
provenance. A keyed preference can use a JSON data file such as
`{"key":"headings"}`. Do not invent confirmed provenance or store credentials.

```text
python3 <runtime>/hub.py --workspace <workspace> remember --kind rule --title <title> --file <body-md> --data-file <data-json> --scope project --scope-key <project-key>
python3 <runtime>/hub.py --workspace <workspace> save --kind note --title <title> --file <body-md> --item <existing-item-id> --parent <baseline-revision-id>
```

Team scope omits its key. Repeat `--tag` for discovery; `--artifact name=absolute-file`
explicitly preserves a chosen attachment. Core studio saves already include their
actual writing artifacts; do not separately publish duplicate generic articles.

## Correct or stop using shared memory

Read the exact current revision first. For a correction, use `save` with the same
item, kind, scope/key, tags and data, and `--parent` set to the read revision; change
only the requested content. Concurrent heads need explicit resolution, not an
implicit overwrite. For “forget this for the team,” use `remove` with the same
identity/kind/scope and explicit parent. It creates a tombstone excluded from new
search/context; it does not erase Git history or update other authors' article pins.
Explain that distinction before promising deletion. Never rewrite Git history.

For “stop using this in this article,” detach the selected item through
[article context controls](../workspace/context.md); do not retire it for everyone.
After changing a shared rule, offer adoption for this article; leave other pins
unchanged. Report queued/pending-review status until the change reaches shared main.
