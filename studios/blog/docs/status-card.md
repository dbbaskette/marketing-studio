# Your Blog Studio status card

In your Codex or Claude chat, say:

> Show status.

Or choose a blog:

> Continue [blog title].

Blog Studio uses the current blog. If more than one blog matches, it asks you to
choose. The card appears in chat; there is no separate dashboard to open.

Example:

> **A clearer engineering handoff**
>
> draft · Google: Not linked
>
> Local: saved · Hub (last known): local only
>
> Last checked: Not checked
>
> Last confirmed saved to Hub: Not confirmed
>
> **Next:** Proofread the draft.

A linked blog also shows **Google Doc** and, when shared, **GitHub copy** links.
For linked Docs, a live check reports In sync, Google has changes, Local changes
pending, Both changed, or Not checked. Offline observations remain historical.
The Hub line distinguishes local-only, queued, pending review, shared, conflicts,
and unavailable state. A previous confirmed save is not proof that newer edits
have reached the team.

Other useful requests:

- **Is everything saved?** Refresh the selected Hub when available and inspect save status.
- **What changed?** Compare with the previous local checkpoint.
- **What changed in Google?** Read and compare Google against the saved transfer baseline.
- **Show my defaults.** Inspect author, audience, voice, blog type, and review folder defaults.
- **Remember my default audience is platform engineers.** Save a personal workspace default.
- **Undo that edit.** Restore the selected earlier text as a new revision, preserving history.

Undo keeps current voice/source/guidance selections. It does not overwrite the
Google Doc; ask to push when ready to send the restored wording there.

## Get the new commands

These helpers require runtime **1.7.0**. After installing a trusted release bundle,
start a new Codex or Claude session. A routine writing-guidance refresh does not
install executable helpers. Existing articles retain their writing guidance pins;
the updated installed entrypoint supplies the status and recovery operations.

For a local source checkout or an extracted offline skill, the direct helper is:

```sh
python3 skills/blog-studio/scripts/studio.py --root /absolute/path/to/.blog-studio status --format markdown
```

For a managed install, use the installed runtime and interpreter recorded in its
configuration. The chat skill handles these paths for you.

[Prompt cheat sheet](prompt-cheat-sheet.md) · [Setup](installation.md) · [README](https://github.com/dbbaskette/blog-studio#readme)
