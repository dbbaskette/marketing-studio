# Blog Studio packages

Blog Studio ships as one skill folder, [`skills/blog-studio/`](skills/blog-studio/SKILL.md):
the entry file, its references and the Python helpers. What is installed is
what is used; nothing is fetched while an author writes. Each release publishes
three archives on the repository's
[Releases page](https://github.com/dbbaskette/blog-studio/releases).

| Archive | Contents | Use |
| --- | --- | --- |
| `blog-studio-installer.zip` | `installer/`, the whole `skills/blog-studio/` folder, and the installation and troubleshooting guides | Recommended. Run `sh installer/install.sh`; see the [installation guide](docs/installation.md). |
| `blog-studio.zip` | The `blog-studio` skill folder alone | Manual install: copy the folder into a skill root yourself. No managed updates or rollback. |
| `blog-writing-toolkit.zip` | The earlier five-module collection | Reference only; see the end of this page. |

Each archive has a `.sha256` file beside it. Do not install the managed and the
manual copy under the same name at once; a tool would discover both.

## Version

[`skills/blog-studio/VERSION`](skills/blog-studio/VERSION) is the only place the
version is written. The build, the installer, the installed manifest, the Team
Hub compatibility check (`hub_store.VERSION`) and the version recorded in each
new blog all read it. A release is a change to that file plus a
[CHANGELOG](CHANGELOG.md) entry.

## What the installer does

The installer copies the skill folder into
`~/.local/share/blog-studio/versions/<version>-<content hash>/`, writes
`install-manifest.json` (version and a SHA-256 for every file) and `config.json`
(the Python that runs the helpers), runs the helpers once in a throwaway
workspace, then points `~/.local/share/blog-studio/current` at the new copy.
`~/.agents/skills/blog-studio` and `~/.claude/skills/blog-studio` are links to
`current`, so an update or rollback is one link switch and both tools always use
the same copy.

A release archive carries a prebuilt manifest and the installer verifies the
folder against it before copying. A source checkout has no manifest, so the
installer computes one. Either way the installed copy is verified against its
own manifest by `check`, by `rollback`, and by the skill's `readiness` command.
Because each installed version carries its own manifest, any intact version that
was ever installed, including 1.x, stays valid for rollback; the installer keeps
no list of known releases.

The manifest proves that files are complete and unchanged since the build. It
does not prove who built them. Authenticity comes from downloading the archive
from this repository's Releases page.

## Build and release

```sh
python3 scripts/build.py            # writes build/*.zip and build/*.zip.sha256
python3 scripts/build.py --check    # builds twice in a temp folder and verifies the result
```

`build/` is ignored by Git; archives are never committed. The build has one
include list, sorts entries, and stamps a fixed time and mode, so the same tree
produces the same bytes on the same Python build. It never writes into the
source tree.

Merging a change to `VERSION` into `main` runs
[`release.yml`](.github/workflows/release.yml): if tag `v<VERSION>` does not
exist yet, it runs the checks, builds, and creates the tag and its GitHub
Release with the archives, checksums and that version's changelog section.
See the [developer guide](docs/development.md).

## Team Hub and writing data

Author work lives in a workspace, by default `.blog-studio` under the writing
project, and optionally in a separate private Team Hub repository. Neither is
part of any package. Each blog records the Blog Studio version it was started
with, and adopting a newer version for a blog marks its earlier reviews stale.

## Upgrading 1.x installations

Version 1.x installed a small bootstrap that fetched guidance from `main` at
the start of each blog. [`guidance/manifest.json`](guidance/manifest.json)
remains only for those installations: it declares a minimum runtime of 2.0.0,
so a 1.x bootstrap reports that it needs the installer update. Running the
current installer upgrades the managed installation in place.

---

# Blog writing toolkit (reference)

[`skills/blog-writing-toolkit/`](skills/blog-writing-toolkit/SKILL.md) is the
original collection of five source modules that Blog Studio grew from:
`content-strategy`, `blog-write`, `copywriting`, `copy-editing` and `blog`. It
has one entry point, five module wrappers and unchanged upstream snapshots with
licenses and commit/hash records in
[sources.lock.json](skills/blog-writing-toolkit/sources.lock.json). Blog Studio
does not load it. It is kept for provenance and built as
`blog-writing-toolkit.zip`; to use it, copy the whole folder into a skill root.
`python3 skills/blog-writing-toolkit/scripts/validate_package.py` checks its
hashes, licenses and links. The upstream claims and examples it contains need
ordinary fact checking before use.
