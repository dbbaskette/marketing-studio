# Short requests use saved context

Use this for short workflow requests, not a new intake interview. Resolve the
current article from this conversation first; `select --id <id>` persists the
choice for later sessions. If none is established, `route` uses the saved selection
or the only article. Never choose arbitrarily among duplicate titles.

```text
python3 <runtime>/studio.py --root <workspace> route "Pull and proofread" --id <id>
```

The helper returns a plan, not evidence of execution. Read its focused references
and perform the actions in order using existing writing/Google/Hub helpers.
For synonyms outside its small alias set, infer ordinary intent and use the same
routes. Bare “push”/“pull” needs a destination if context cannot distinguish Google
from Git; pass `--destination google|hub` only when already established.

- **Proofread:** correct spelling, grammar, punctuation; keep facts, author voice,
  and structure. Use [exact-input diagnostics](workspace/performance.md) when
  repeating mechanical checks. Read the current draft and save with `article save ... --label
  proofread`. Do not expand to research or a developmental rewrite.
- **Push to Google Docs:** reuse the linked Doc. On first handoff, use the selected
  review-folder preference if present; obtain missing destination/access details.
  Read current Google state, handle conflicts, preserve formatting, and verify
  before checkpointing. The request authorizes the selected transfer, not sharing
  changes or sending background material.
- **Pull from Google Docs:** return accepted text and formatted snapshots through
  the existing return contract. Pull does not accept suggestions or push back.
- **Pull and proofread:** complete and verify return first, then proofread locally.
  If return is blocked/conflicted, resolve it before editing a potentially stale copy.
- **Save and sync:** save completed selected work and its dependencies to the selected
  Hub; without a Hub, save locally and report that. Report queued/review/conflict
  states accurately. Do not sweep unrelated workspace content.
- **Continue:** use `resume --id <id>` once for compact context and the status card;
  use [focused context](workspace/performance.md) for needed passages.
- **Show status:** show the [status card](workspace/status.md).
- **What changed / Undo that edit:** use [comparison and recovery](workspace/changes.md).
- **Clear local caches:** use `cache --clear`; writing and history remain.
- **Show/change my defaults:** use [defaults](workspace/defaults.md).

After a completed operation show a short result; open the full status card when
requested or on resume. Never require the user to repeat formatting, checkpoint,
privacy, or verification instructions already supplied by the skill.

**“Push as suggestions”** loads [Google suggestions](google/suggestions.md). Refresh the linked Doc first, reconcile conflicts, then post selected findings as guarded native suggestions/comments. Requires installed runtime 1.9+.
