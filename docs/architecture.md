# Marketing Studio architecture

Marketing Studio is a small local Python application with a browser UI. It is an
umbrella for three independent installations, not a repository merger. This scope
supersedes the earlier monorepo proposal for the current implementation.

## Responsibilities

`marketing_studio/page.py` exposes the home page, first-run setup, settings,
installation paths, a computer inventory, and studio launch actions. The page
uses the studios' existing CSS and adds its own shell and launch cards.

`shared.py` reads and atomically updates the existing schema-1 studios config.
Writers serialize on its adjacent `.lock` file. Edits preserve unrelated JSON
bytes and unknown keys. A form sends its previous values so conflicting edits
can be refused. `local.root` is an additive group that older studios ignore.

`home.json` under Marketing Studio's data folder contains only setup completion
and optional installation paths. It never caches shared settings or session keys.
`STUDIOS_CONFIG` and `MARKETING_STUDIO_DATA` override file locations for tests.

`catalog.py` discovers sibling repositories and installed runtime folders, or
uses explicitly configured paths. `<PRODUCT>_STUDIO_INSTALL` environment variables
can select installations for tests or development. Each product name is written
in full, uppercase with underscores, for example `TRAINING_STUDIO_INSTALL`.

`launcher.py` starts a child interpreter for each requested studio and reuses
its in-memory link on later Open actions. Each named browser tab can return to
the running studio. A failed start is terminated and can be retried. Closing
Marketing Studio stops only its children and their process groups.

`bridge.py` adapts existing native Python interfaces in that child interpreter.
It initializes an unconfigured workspace through the studio's own Git helper and
stores native preferences, including Blog Studio's private defaults. Preparation
is idempotent. Existing workspaces and local choices remain in place.
Presentation Studio and Training Studio retain their existing singleton locks
and restart-token handoff. Blog Studio uses its native installation lease,
workspace lock, page server, runner, and cleanup, with a private announcement to
the parent. The bridge starts no agent during setup.

## Lifecycle

1. First launch reads existing shared preferences and shows setup.
2. Each Continue action saves only fields changed in that step.
3. Finish prepares installed studios, then marks setup complete. Failed
   preparation leaves completion false; successfully prepared studios are safe to
   revisit on retry.
4. Later launches show the three product launchers.
5. Open initializes a newly installed studio if needed, then serves its native UI.
6. Each independent launcher can use the native preferences after preparation.

A changed workspace default never moves existing work. A remote is optional.
Local work uses separate Git repositories to avoid concurrent studios competing
over one index and HEAD. Remote mode keeps each studio's native separate-clone
behavior and content folder conventions.

## Local access

The server binds only to IPv4 loopback. Host validation, a per-session token on
API requests, same-origin JSON POSTs, a 64 KB request limit, CSP, no-referrer,
no-store, and frame denial use the existing Presentation Studio server contract.
The browser receives a token in a fragment and stores it only in session storage.
The CLI shows a full link only in a person's terminal. Nonterminal output contains
an address without its key, and normally opens the browser for the person.

Child links travel over a pipe and stay in memory. Standard error goes to
per-product launch logs in Marketing Studio's data folder. No studio dependency,
brand skill, or provider is installed by setup. The computer inventory is offline;
studios perform their own sign-in checks when opened.

## Compatibility

The shared model and reasoning defaults are supported by Presentation Studio and
Training Studio. Blog Studio currently supports the shared assistant and author,
and uses that assistant CLI's model settings. This UI makes that limit explicit.
The application does not claim per-task model routing that the studios do not
implement. Existing items keep their own saved input choices.
