# Marketing Studio architecture

One repository contains Marketing Studio and three independently runnable studios.
Each studio retains its native commands, pipeline, tests, skill entry, installer,
and data locations. The suite can install any selection; it also distributes a
self-contained installer archive for each studio.

## Repository boundaries

| Directory | Responsibility |
| --- | --- |
| `marketing_studio/` | Home page, shared setup, launch coordination, and user CLI |
| `studios/blog/` | Blog Studio pipeline and native interfaces |
| `studios/presentation/` | Presentation Studio pipeline and native interfaces |
| `studios/training/` | Training Studio pipeline and native interfaces |
| `core/studio_core/` | Shared settings storage, page-server protections, companion installation, and packaging |
| `ui-kit/` | Common stylesheet and safe Markdown renderer |
| `pins/companions.json` | Canonical companion revisions and integrity hashes |
| `installer/` | Suite/subset install orchestration and restoration |

Original histories are imported under the studio directories. Old branches and
tags use product-name namespaces. Commit maps and original tree hashes are in
`docs/migration/`. Unfinished Blog Studio research changes are preserved on
`migration/blog-studio/preserved-working-tree`, separate from main.

## Shared infrastructure

The settings implementation comes from Training Studio's compatible lossless
writer, including its under-lock callable update API. Product facades supply the
product name, exception type, and address validation. They retain independently
patchable module contexts, so importing two products cannot change one another's
configuration. Blog Studio retains its validation and legacy migration API while
using the shared leaf-patching implementation. Existing shared settings remain in
`~/.config/studios-config.json`, with the same adjacent lock and merge semantics.

Marketing Studio and Presentation Studio use the shared loopback server directly.
Training Studio inherits its protocol checks and retains its domain-specific reads
and writes. Blog Studio retains its specialized server and stronger existing CSP,
its workspace lock, timeouts, and content limits. Its protocol is not flattened
into the other studios' contract.

The native installers share pinned companion fetching, integrity checks, and
installation functions. Their compatibility bindings preserve native exception
classes and existing injection points. The suite invokes one companion pass for
the selected tools. Installing software remains an explicit installer action.

Code and identical UI files are linked within the checkout. Packaging permits
only the named suite-owned links, traverses their shared targets, and writes
ordinary files into every released archive and installed runtime. Unexpected
links remain refused. No installed studio needs the source checkout, another
studio, or a shared external core installation.

## Settings and launch lifecycle

First run reads existing shared choices and opens setup. Continue saves only
changed fields. Finish prepares installed, unconfigured studios through their
native workspace helpers and records completion in Marketing Studio's `home.json`.
Preparation starts no assistant job and never moves an existing workspace.

Local Git is the default. Separate local repositories avoid contention over an
index and HEAD. Remote mode retains each studio's native clone and content-folder
conventions. Native data directories and assistant skill locations are unchanged.

Marketing Studio discovers bundled source studios first when run from a checkout.
A managed suite prefers native installed copies so both launchers run the same
version. Explicit installation paths remain authoritative. Child links stay in
memory and travel through private pipes. Closing Marketing Studio stops only
process groups it started.

The user CLI offers open, setup, status, doctor, install, update, rollback, and
uninstall. Repeated open/setup commands contact a same-user Unix socket with mode
0600 and reuse the running app. Socket messages are bounded and contain no session
keys. Long custom data paths use a verified private short-path directory. Status
and doctor neither start the app nor contact providers.

## Installation and updates

The suite installer stages a content-addressed runtime, uses the native installers
for the requested studios, writes the umbrella launcher and `~/.local/bin` command,
and records the managed pointers. It snapshots only known installation metadata,
launchers, and skill links for failure recovery and rollback. Workspace content
and settings are excluded from these writes. Running studios block installation.
A repeated install of identical content retains the previous rollback record.

The installed studios remain usable through their own commands and double-click
launchers. Uninstalling Marketing Studio leaves them in place. Updates use a
newer downloaded suite or subset installer; suite-managed native update buttons
defer to that installer to keep shared dependencies consistent.

New guidance comes from this repository at explicit studio manifest paths. Old
or custom sources retain their existing layout, and old repositories remain
readable after retirement. Archived release downloads continue to work.

## Verification

One root check runs the home/core/installer suite, every native studio suite and
validator, Blog Studio's pinned lint/build checks, native setup and launch checks,
and synthetic Hub journeys. The shared Tart runner owns disposable VM lifecycle
and retains logs. No test uses real team content or starts paid provider work.
