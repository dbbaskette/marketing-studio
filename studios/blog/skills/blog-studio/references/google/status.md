# Is this the newest copy?

Keep one stable linked Google Doc per blog. The document ID and fresh comparison
identify the working copy; a title or milestone name cannot prove freshness.
Load this reference when resuming a linked article or asking which copy is current.

Runtime 1.6 adds:

```text
... studio.py --root <workspace> google status --id <article> --kind draft --online
```

Use `outline` for an outline-only task. The optional `--account` selects an already
signed-in gcloud account without switching it. This checks the saved Doc through
native read-only calls; it never exports, edits, accepts suggestions, logs in or
saves a manuscript. Only a machine-local check cache changes. No Google access or
network means **Not checked**, never “In sync.” Keep writing locally when appropriate.

| Status | Meaning and next step |
| --- | --- |
| In sync | Live text/formatting and local content match the saved baseline; continue |
| Google has changes | Bring the team's edits/formatting back |
| Local changes pending | Send the selected local edits when requested |
| Both changed | Compare and reconcile before sending; changes may overlap or have converged |
| Suggestions pending | Runtime 1.9+: accepted text matches; review pending Google suggestions, then pull |
| Not checked | No fresh comparable read; resolve access, scope or baseline when needed |

The live check uses the native formatting fingerprint established by the formatted
return workflow. Older text-only baselines need one inspected formatted return.
Runtime 1.9 separates pending suggestions from accepted text and reports review
counts after a stable native read. Changed tab scope or failed/incomplete reads
remain Not checked. A status
is true at its check time, not a guarantee against later edits. Writes still need
fresh revision guards. A connector-only session uses its fresh read and the existing
compare contract; if equivalent evidence is unavailable, report Not checked rather
than installing or logging into another provider automatically.

Show the status, **Last checked**, and **Last confirmed saved to Hub** in the resume
checkpoint. Include the linked Doc and a relevant next action. Offline `google status`
and `context` always report Not checked; their last-known result is historical.
A failed attempt retains the last successful check separately. Hub timestamps are
when this machine confirmed a revision on remote main, not reconstructed Git
commit times. Unknown is unknown; queued/offline/review-branch work is not saved to
main. A newer pending revision does not replace the prior confirmed-save timestamp.

## Named milestones

Suggest “Draft ready for review,” “Team edits incorporated,” or “Approved for
publication” at meaningful checkpoints, only when the author has actually reached
that stage. Name the current version in Google Docs via File → Version history →
Name current version. This release does not automate Google's version-name UI or
create numbered document copies. Do not call a version approved without the author's
approval. The Doc title/link stays stable, and a label does not imply a Hub save.

[Google version history](https://support.google.com/docs/answer/190843).
