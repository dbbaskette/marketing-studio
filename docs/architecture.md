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
| `core/studio_core/` | Shared settings storage, page-server protections, companion installation, packaging, and the desk parts (`drafting/`, `text_checks.py`, `step_times.py`) |
| `ui-kit/` | Common stylesheet (with the desk's styles), safe Markdown renderer, and the desk's page kit (`drafting.js`) |
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
and writes. Blog Studio reuses the loopback bind method to avoid DNS during startup. It retains
its specialized server and stronger existing CSP,
its workspace lock, timeouts, and content limits. Its protocol is not flattened
into the other studios' contract.

The native installers share companion requirement resolution, exact-lock fetching, integrity checks, and
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
native workspace helpers and records `setup.version: 1` in the shared
`studios-config.json`. Independent launches use the same completion record and
setup UI, bundled in `studio_core`; Marketing Studio need not be running or
installed. A partial or invalid file always requires setup. Earlier completed
Marketing Studio setup is promoted on opening it.

A studio launched after setup adopts the shared workspace choice only if it has
none. Standalone setup prepares the current studio; later launches prepare the
others. Every shared write holds the adjacent config lock and preserves unrelated
values. Finishing refuses a conflicting change made while workspace preparation
was in progress. Model and reasoning choices reach all three studio workers.
`render.previews` and `brand.skill` are also shared; absent previews follow the
delivery format after setup (local for PowerPoint, Google Drive for Google output).
Existing private preview and brand-path choices migrate without replacing shared
choices. Content-specific defaults, limits, notifications and update preferences
remain optional native controls.
Preparation starts no assistant job and never moves an existing workspace.

When Marketing Studio opens a studio, it names its own tab and passes its address in
the link's fragment. The studio accepts that address only for the same host on another
port, and shows a "Marketing Studio" item that brings the tab forward. A Marketing
Studio tab without its key asks the person to run `marketing-studio` again.

Local Git is the default. Separate local repositories avoid contention over an
index and HEAD. Remote mode retains each studio's native clone and content-folder
conventions. Native data directories and assistant skill locations are unchanged.

Marketing Studio discovers bundled source studios first when run from a checkout;
`status` names each studio's folder and version and marks Git checkout copies.
A managed suite prefers native installed copies so both launchers run the same
version. Explicit installation paths remain authoritative. Child links stay in
memory and travel through private pipes. Closing Marketing Studio stops only
process groups it started. Each launch writes the studio's standard error to
`logs/<studio>.log` in the Marketing Studio data folder and keeps the launch before
it as `<studio>.previous.log`. A studio that stops or times out before opening is
reported with that log's path and its last 12 lines.

The user CLI offers open, setup, status, doctor, install, update, rollback, and
uninstall. Repeated open/setup commands contact a same-user Unix socket with mode
0600 and reuse the running app. Socket messages are bounded and contain no session
keys. Long custom data paths use a verified private short-path directory. Status
and doctor neither start the app nor contact providers.

`serve` runs the home server without opening a browser. When the first browser or
studio open fails, including on a computer without a screen, the server keeps
running: a terminal is shown the reason with the private link, and a pipe is
given the reason in its JSON line without the session key.

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

## Private release runtimes

Platform bundles add `runtime/`, prepared `companions/`, and `distribution.json` to
the ordinary suite inventory. `pins/runtimes.json` pins runtime downloads and Python
dependency notices by SHA-256; the ordinary bundle manifest also covers their extracted
files. Release preparation runs in a disposable HOME with user npm configuration
excluded and lifecycle scripts disabled. Application code remains standard-library
Python with no frontend build step.

Installation runs each native installer with Python from the retained suite version.
Generated native launchers prepend that version's private Python/Node paths. Prepared
companions are copied to upstream version folders and linked through upstream discovery
paths under their existing install locks. No npm command or companion download is needed
on the user's computer. Workspaces, assistant sign-ins and gcloud remain external.

## Background start and stop

`marketing-studio start` runs `marketing-studio serve` detached, in its own session,
with output appended to `home.log`, and waits until the private control socket
answers. `start`, `stop` and `restart` then use that same-user socket (state,
start, stop, shutdown); a shutdown is answered first, then stopped the way Ctrl-C
does, so the server closes its control socket, network listeners and studios in order.

Each studio child is recorded in the data folder's `run/` folder with its process
and start time, never its link. A stop first lists assistant jobs (codex, claude or
gemini processes under the studio) and refuses unless `--force` is given. A studio
left running by a Marketing Studio that stopped abruptly is stopped at the next
start, unless it has a running job, and by `stop --all`. Only a recorded process
that still runs this data folder's studio bridge is ever signalled.

## Optional local-network access

`marketing-studio serve --lan` (or `start --lan`) adds fixed-destination bridges on one private IPv4
interface. Native servers continue to bind loopback and validate their original
session keys and origins. Each studio keeps its own browser origin, assets, API
routes, and session storage. Marketing Studio returns the bridge's private link
when a phone launches a studio. Bridges validate incoming Host/Origin and session
headers before translating the origin to the fixed loopback destination; they
never accept arbitrary proxy destinations. The listeners are owned by the umbrella
process and close on shutdown. The default CLI mode remains loopback-only.
Network mode is HTTP on a trusted LAN; see [the access boundary](local-network.md).

## Shared research contract

All three studios explicitly integrate the purpose-led, independently reviewed
Harness Research schema-2 bundle. See [the handoff and compatibility contract](research-synthesis.md).
