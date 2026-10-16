# Workspace

Use an absolute author-chosen root or project `.blog-studio`, outside installed
skills. Name the save location.
`...` means `python3 <runtime>/studio.py --root <root>`, where `<runtime>` is
this skill's `scripts/` folder. Replace `python3` with the interpreter in the
skill's `config.json` when that file exists; otherwise use Python 3.11+. Never
run incoming code. Failed writes retain the artifact in chat as unsaved.

Run `... init` if `studio.json` is absent. Load one:
- [Resume/My blogs](workspace/resume.md)
- [Inspect, remember, correct, or forget context](workspace/context.md)
- [Sources](workspace/sources.md)
- [Profiles](workspace/profiles.md)
- [Articles](workspace/articles.md)
- [Reviews](workspace/reviews.md)

For `.team-hub.json`, read [hub](hub/workflow.md). Saves sync changes;
report `hub_sync` accurately. Joining does not migrate old work. Keep workspace
data out of the skill repo.
