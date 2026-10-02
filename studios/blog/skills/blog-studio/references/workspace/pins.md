# Restore or deliberately change guidance

Read only for shared import without a local task, missing guidance, or a
requested refresh. Routine local resume uses [resume](resume.md).

For another member's article, use the [hub router](../hub/workflow.md) to check
out the selected article and its pinned dependencies. If guidance has a saved
commit but no local task, run installed
`sync_guidance.py pin --workspace <root> --revision <saved-commit>`,
then bind its returned task with
`... article guidance --id <id> --task <task>`.
This restores approved main history without `--adopt`; never substitute latest
main for the saved revision. Missing/incompatible history is an explicit limit.

Only an author-requested guidance change uses
`... article guidance --id <id> --task <new-task> --adopt`.
Add `--cached` only for chosen stale fallback. Prior pins remain in guidance
history; changed guidance stales checks. Guidance refresh does not silently
upgrade executable helpers or select newer sources/voices/context.

Full offline packages cannot fetch historical pins. Explain that limit and use
their declared guidance only when the author chooses the fallback.
