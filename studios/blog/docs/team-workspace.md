# Share blogs through a studios repository

Use the same team repository address in Training Studio, Blog Studio and
Presentation Studio. The [shared convention](shared-studios.md) describes the
folder layout and shared defaults.

On **Settings** or **Status**, open **Join our team repository**. Enter its Git
address and branch, or use the values pre-filled from shared studios defaults.
Git must already have your name, email and repository access configured. The
studio never changes your global Git configuration. Local writing needs no Git.
Choose **After every decision** or **Only when I choose Share now**. Check the
shared-defaults option only if you want changed team values used by other studios.

Joining opens the writing page on Blog Studio's own clone. The permanent launcher
remembers it. Another studio's checkout is never reused. The branch should allow
direct team commits; contribution PRs belong to the legacy Hub flow.

## Drivers and sharing

A newly created blog is claimed and its claim is shared before a worker can run.
On another computer it can be read; use **Take over** explicitly to become its
driver. **Hand over** stops work on this computer and shares the released claim.
A blog with nobody driving it offers **Take this blog**. A takeover preserves
unshared work on the old computer under `refs/blog-studio/kept/` when it reconnects.
Use `git show <ref>:blogs/<id>/DRAFT.md` in that clone to inspect preserved writing.

Use **Status → Share now** to retry an offline save or share manual-mode decisions.
A current driver may save while offline, but cannot establish a new claim offline.
Local edits made outside recorded studio decisions stop sync with the changed
paths named; commit them deliberately with Git before retrying. They are not
silently overwritten or published. Each blog has a readable folder and README.
Sources, voices and team memory live under `blogs/.shared/`.

When all planned stages are approved, **Publish revision** records a numbered,
immutable tag in the team repository. This does not publish a website.

## In a conversation or terminal

Use Python 3.11+ and the installed helper (`blog`) in place of this source path:

```sh
python3 skills/blog-studio/scripts/studio.py --root /absolute/local-writing team join --repository https://github.com/example/team-studios.git
python3 skills/blog-studio/scripts/studio.py --root /absolute/clone/blogs team status
python3 skills/blog-studio/scripts/studio.py --root /absolute/clone/blogs team sync
python3 skills/blog-studio/scripts/studio.py --root /absolute/clone/blogs team take --id blog-id
python3 skills/blog-studio/scripts/studio.py --root /absolute/clone/blogs team takeover --id blog-id
python3 skills/blog-studio/scripts/studio.py --root /absolute/clone/blogs team handover --id blog-id
python3 skills/blog-studio/scripts/studio.py --root /absolute/clone/blogs team publish --id blog-id
```

`team join` returns the actual clone workspace. Use that path for later commands.
Ordinary source, profile, article and guided-run commands work there too. A
conversation must respect the same driver; it cannot edit a blog driven elsewhere.

## Bring selected work from a legacy Team Hub

Existing Team Hubs remain readable through their existing commands. Migration is
explicit; opening the page or joining a team never moves old work automatically.
Join the destination first, then name the old local workspace and selected IDs:

```sh
python3 skills/blog-studio/scripts/studio.py --root /absolute/clone/blogs team migrate --from-workspace /absolute/old-writing --article selected-blog-id
```

Selected local blog folders and their referenced sources and voices are copied
without changing their bytes or identities. Selected legacy immutable revisions
and their dependencies are retained under `.shared/legacy/`; selected memory is
readable under `.shared/memory/`. Native Google captures stay local. The old Hub
and its Git history are never changed or refreshed. Migration refuses existing
destination folders and archives. Existing local work is kept on any refusal.

Use `--source`, `--profile` or `--memory` to migrate explicitly selected standalone
references, voices or legacy memory items. Each option may be repeated.

Shared defaults currently supply Blog Studio's author, assistant agent, team
repository, branch and sharing choice. Model, effort, brand and output settings
are retained for studios that use them; Blog Studio's worker uses its CLI's model
configuration. Changing author or assistant in Settings offers an unchecked
**Use changed author and assistant defaults for all studios** choice.
