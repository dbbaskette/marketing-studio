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

## Optional local-network access

`marketing-studio serve --lan` adds fixed-destination bridges on one private IPv4
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
