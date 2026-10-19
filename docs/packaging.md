# Package and install the studios

Every product has the same two entry points in its source folder:

| Product | Source folder | Build its installer | Install it |
| --- | --- | --- | --- |
| Marketing Studio, including all three studios | Repository root | `bash package.sh` | `bash install.sh` |
| Blog Studio | `studios/blog/` | `bash package.sh` | `bash install.sh` |
| Presentation Studio | `studios/presentation/` | `bash package.sh` | `bash install.sh` |
| Training Studio | `studios/training/` | `bash package.sh` | `bash install.sh` |

Run the commands from the folder in the table. They also work with an absolute
script path from another directory. Packaging builds a ZIP; it never installs or
starts a studio. Installation is a separate explicit action.

## Build a bundle

The consistent packagers currently target **Apple Silicon, macOS 13+**. They use
the existing local bundle model: private Python and Node, prepared skills and the
brand selected by your source configuration. Codex and Claude Code are supplied
and signed in separately on the destination computer. Blog Studio includes
Harness Research; Presentation Studio, Training Studio and Marketing Studio also
include Harness Slides and its production dependencies and image tools.

From the repository root:

```sh
bash package.sh                            # Marketing Studio and all three studios
bash studios/blog/package.sh               # Blog Studio only
bash studios/presentation/package.sh       # Presentation Studio only
bash studios/training/package.sh           # Training Studio only
```

All four packagers accept the same options:

```sh
bash package.sh --plan
bash package.sh --mode offline
bash package.sh --config /path/to/sources.json --output /path/to/local/bundles
bash package.sh --verify /path/to/bundle.zip
```

Online bundles include the studios, skills, brand and private Python/Node. Setup
downloads pinned Google and local preview tools into private directories.
Offline bundles carry those tools too. Nothing uses system Python or Node during
bundled installation, and setup never installs an assistant or starts a provider job.
Packaging needs an existing Python 3.11+, Git, Node 22+ and npm on the build computer;
it can build and verify Apple Silicon archives on an Intel Mac. Native execution
and account access still require destination testing.

Outputs default to `~/LocalBundles/<product>-studio/`. Every ZIP has a checksum
sidecar and an internal manifest. Generated bundles and caches stay local;
checkout output paths are allowed only under the ignored `build/` or `dist/` folders.
To share a build cache between products, pass the same `--cache` directory.

## One source configuration

Create the ignored local configuration once:

```sh
bash package.sh --init-config
```

Edit `studio-package.local.json`. It uses the format in
[`studio-package.example.json`](../studio-package.example.json): Git URLs with
optional refs, or local Git checkout paths for Harness Research, Harness Slides
and the brand. Every product reads this same file. Blog Studio leaves the slide
source out of its package. Config paths, credentials, workspaces and Git identity
are excluded from the bundles. An explicit `--config` selects another file.

The old `presentation-studio-package.local.json` filename remains a fallback when
the shared file is absent. `presentation-studio-package` remains an alias for the
Presentation Studio packager. Existing `scripts/build_bundles.py` commands remain
available for source-only ZIPs and unbranded platform downloads on other systems;
see [installation](installation.md#build-downloads). Source-only installers require
system prerequisites, unlike the local bundles described here.

To use one CLI from any directory:

```sh
bash package.sh --install-cli
studio-package marketing --plan
studio-package blog
studio-package presentation
studio-package training
```

## Install a built bundle

Extract the complete ZIP and open Terminal in its **outermost folder**, beside
`START HERE.txt`, `local-manifest.json` and `install.sh`:

```sh
bash install.sh
```

The filename and location are identical in all four downloads. The Marketing
Studio ZIP installs all three studios; each individual ZIP installs only its own
studio and required shared components. A Marketing Studio bundle also accepts
`bash install.sh --studios blog` to install a selection. Independent studio
launchers remain available; existing workspaces and settings are preserved.

`installer/` and `studio/` hold implementation files. Nested shell entry points
forward to the same bundle setup, but there is no need to search inside them.
`.command` files are optional compatibility launchers. Packaging scripts are for
the source checkout and are not required on the destination computer.

The [local bundle guide](local-presentation-bundle.md) explains component pins,
cache integrity, tool downloads, sign-in and offline verification in more detail.

If an older bundle reports an integrity failure under Python's `__pycache__`
folder, extract a fresh copy of the ZIP into a new folder and run
`PYTHONDONTWRITEBYTECODE=1 bash install.sh` from its outermost folder. A failed
attempt may already have rewritten caches, so retrying in that same folder is
not sufficient. Regenerated bundles omit runtime bytecode caches and disable
cache writes during installation. Integrity checks still verify every packaged
file; use a fresh download for other checksum failures.
