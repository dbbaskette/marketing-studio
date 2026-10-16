# Shared studios workspace

A team can keep trainings, blogs and presentations in one repository. Blog Studio
owns `blogs/` in its own clone, with plain blog folders and `.shared/` references,
voices and memory. Other studios’ folders are never staged by Blog Studio.

Use `<python> <runtime>/studio.py --root <workspace> team join --repository <address>`
to join. The result names the actual writing root for later commands. Optional
`--branch main` and `--share decision|asked` choose the branch and sharing mode.
A local writing workspace remains usable without Git or a team repository.

`team status` reads the connection. `team sync` shares pending commits and brings
in teammates’ changes. A blog has one driver. `team take --id <id>` takes an
unclaimed blog; `team takeover --id <id>` explicitly replaces its current driver;
`team handover --id <id>` shares its release. Never edit or run work claimed by
another computer. New claims must reach the remote before work starts. A current
driver may save offline and retry sharing. A takeover keeps the old computer’s
unshared commits under `refs/blog-studio/kept/` when it reconnects. Local changes
outside recorded decisions stop sync rather than being overwritten.

`team publish --id <id>` marks an approved guided blog as a numbered revision.
It does not send it to a publisher or change repository visibility.

For explicit migration, use `team migrate --from-workspace <legacy-workspace>
--article <selected-id>` (repeat `--article` for each selected blog). It copies
selected writing, referenced sources and voices, and archives selected immutable
legacy history and memory. The source workspace and Hub are only read. Existing
destination work is never replaced. Keep the returned root and selected IDs.

Shared defaults are optional in `~/.config/studios-config.json`, overridden by
`STUDIOS_CONFIG`. Local studio settings win. Blog Studio reads person name,
assistant agent, team repository/branch and sharing choice. Other fields remain
untouched. Only the person’s explicit “use for all studios” choice permits a
merged write of changed shared fields. Missing or bad config never blocks writing.
