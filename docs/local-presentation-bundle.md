# Rebuild the local Presentation Studio bundle

The build recipe lives in the repository. Generated ZIPs, download caches and
Tanzu Brand assets stay local. The first target is **Apple Silicon, macOS 13+**;
you can build and verify its archive on an Intel Mac. Native execution and
account access still need testing on the destination Mac.

From the Marketing Studio checkout, install the packaging command once:

```sh
./presentation-studio-package --install-cli
```

Then build from any directory:

```sh
presentation-studio-package
```

The default **online** bundle includes Presentation Studio, its skills and brand,
private Python and Node, and prepared slide dependencies. It is about **138 MB**
with the current Tanzu Brand assets. On the destination Mac, explicit installation
downloads the pinned LibreOffice, Poppler/Git dependency closure, Micromamba and
Google Cloud CLI: about **427 MB** on a fresh Mac. No Python, Node, npm, skill or
assistant installation is downloaded during setup. Google and image tools are
included; account sign-in and API credentials remain destination tasks.

For a destination without internet access, include all tools in the ZIP:

```sh
presentation-studio-package --mode offline
```

The offline bundle is about **585 MB** with the current components. Both modes
use the same exact tool versions, checksum checks and private installation paths.
The smaller online ZIP mainly reduces the file you distribute; it does not
remove the eventual tool downloads. Sizes vary with component updates.

The command selects an existing Python 3.11+ automatically, including an
interpreter already managed by uv. It does not download Python. Node.js 22+,
npm and Git are still build prerequisites. You can also run
`./presentation-studio-package` directly from the checkout without installing it.

Installation creates a link in `~/.local/bin` to this checkout, so subsequent
source updates are used automatically. Keep the checkout in place. Existing
unrelated commands are preserved. If `~/.local/bin` is not already on your PATH,
add it to your current terminal with `export PATH="$HOME/.local/bin:$PATH"`.

## Choose the component repositories

Create your local config once:

```sh
presentation-studio-package --init-config
```

Edit `presentation-studio-package.local.json` in the Marketing Studio checkout.
That file is ignored by Git; `presentation-studio-package.example.json` is the
tracked template. Each component accepts a local Git checkout or a Git URL:

```json
{
  "schema": 1,
  "sources": {
    "harness-slides": {"path": "../harness-slides-skill"},
    "harness-research": {
      "git": "https://github.com/dbbaskette/harness-research-skill.git",
      "ref": "v1.0.0"
    },
    "brand": {"path": "../tanzu-brand"}
  }
}
```

Paths are relative to the config file, including when running the command from
another directory. `~` and absolute paths work too. Git sources accept HTTPS,
SSH or file URLs; `ref` can be a branch, tag or commit, and defaults to `HEAD`.
Use a tag or commit for a stable selection. Private repositories use your
existing Git authentication; credentials must not be embedded in URLs.

Local sources must be Git checkout roots. Builds snapshot tracked working files,
including local edits, staged additions and deletions. Add new source files to
the Git index before building. Untracked files, ignored dependencies and Git
account data are excluded. Remote sources use exactly the selected Git ref.
Source checkouts are never reset, cleaned, installed into or updated by packaging.

The default config is discovered beside the packaging CLI in this checkout.
Choose a different file with `--config /path/to/sources.json`; its paths remain
relative to that file. An explicitly requested missing or invalid config fails
instead of falling back. `--plan` reports configured sources without fetching
them; remote versions are resolved only during a build.

Components omitted from the config retain the repository's companion pins and
the sibling `../tanzu-brand` fallback. `--brand` overrides the configured brand
with a local checkout. The brand repository must provide the Tanzu Brand release
packer and installer interfaces. Runtime and extra-tool pins remain separate.

Override the brand or output location explicitly when needed:

```sh
presentation-studio-package \
  --brand /path/to/tanzu-brand \
  --output "$HOME/LocalBundles/presentation-studio"
```

The output defaults to `~/LocalBundles/presentation-studio/`; its `cache/`
directory retains verified downloads. `--cache /path/to/cache` changes that
location. Generated paths inside the checkout are permitted only under the
existing ignored `build/` and `dist/` directories. Building never installs a
studio, changes shared settings, starts a studio, or runs a provider job. Building
may download dependencies. Online builds do not fetch preview or Google tool
archives; those downloads happen during installation. Offline installation uses
only the archive's local dependencies.

A successful build writes a versioned ZIP and a SHA-256 sidecar. The filename
includes the Presentation Studio version, Tanzu Brand version, platform, mode and
content ID. Existing builds are retained; the same inputs reproduce the same
archive. Failed downloads or verification leave earlier archives intact.

## After updating components

- **Presentation Studio and shared Marketing Studio code:** rerun the builder.
  It snapshots the current checkout, including local source edits. Git revision,
  modified status and payload hashes are recorded without absolute source paths.
- **Tanzu Brand:** update the source project and rerun. Its official release
  packer selects and verifies the distributable assets; no installed skill,
  credentials, workspace or arbitrary project files are copied.
- **Configured Harness Slides and Harness Research sources:** update their local
  checkouts or change their Git refs in your local config, then rerun. Builds
  record the exact resolved commits, working-file checksums and modification
  status. Snapshot locks are written only into the bundle, and installation uses
  those bundled files without fetching a moving repository. Config paths and
  credentials are not copied into the bundle.
- **Unconfigured Harness Slides and Harness Research:** update
  `pins/companions.json`, then rerun. To resolve the newest stable releases allowed
  by the existing requirements:

  ```sh
  python3 scripts/update_companions.py --check
  python3 scripts/update_companions.py
  presentation-studio-package
  ```

- **Private Python and Node:** update the exact URLs, versions and SHA-256 values
  in `pins/runtimes.json`, then rerun. Cross-platform slide dependencies must
  remain pure JavaScript, as enforced by the existing release preparation code.
- **LibreOffice, Google Cloud CLI and preview tools:** update
  `pins/presentation-bundle.json`, then rerun. Every archive and conda package has
  an immutable HTTPS URL and SHA-256. When updating Poppler or Git, replace the
  complete resolved `osx-arm64`/`noarch` dependency closure, not only the top-level
  package. For a private trial lock, use `--tools-lock /path/to/lock.json`.

The Google Cloud CLI lock explicitly omits two dangling certificate links in
gsutil's upstream test fixtures. Runtime files and licenses are retained; other
broken or escaping archive links still fail preparation, during installation for
online bundles or during packaging for offline bundles.

The builder does not silently upgrade components. Review and test changes to
locks before distributing a new bundle. A cached download is rechecked on every
build; remove a corrupt cached file and rerun to download it again.

Online installation stores verified tool downloads under
`~/.local/share/presentation-studio-local-bundle/cache/downloads/`. It checks their
SHA-256 on every reuse, retries network failures up to three times, and only
extracts tools after all download checksums pass. Interrupted installation removes
its new incomplete tools directory while preserving earlier installations and
completed downloads. Rerun the installer to retry. If a cached file is corrupt,
remove only the file identified in the error and retry. Installation never uses
Homebrew, installs an assistant or changes system Python and Node.

## Inspect and verify

```sh
presentation-studio-package --plan
presentation-studio-package --verify /path/to/bundle.zip
```

`--plan` prints the mode, versions, sources and paths without downloads or writes.
Archive verification streams every file through its SHA-256 and rejects unsafe paths,
links, duplicate names, missing entries and unexpected files. ZIP permissions
preserve the installation launcher. Packaging does not certify native ARM
execution or live services.

On the destination Mac, extract the ZIP and open **Install Presentation Studio.command**.
Then use `~/Applications/Verify Presentation Studio.command` for offline tool,
brand, PowerPoint, PDF and PNG checks. The verification uses disposable output
and account directories. **Open Presentation Studio Tools.command** opens a
terminal with the private tools for destination sign-in.

Both modes install Presentation Studio, the Marketing Studio launcher/setup,
Harness Slides, Harness Research, Tanzu Brand, private Python/Node,
LibreOffice, Poppler/Git and their native dependencies, Google Cloud CLI, and
Harness Slides' standard Gemini API image tools. The online ZIP contains the
application, skills, brand and runtimes; the remaining tools download during
setup. Arial comes from macOS or your licensed installation.
Codex or Claude Code must already be installed and on PATH;
the bundle reuses the saved assistant choice or detects an available assistant.
Assistant applications are not bundled or installed. The legacy unofficial
Gemini browser route and browser-based brand development audits use separate
optional setup.
Google permissions, assistant sign-in, image API keys and billing belong to the
destination account. No credentials or personal content are packaged.

## Regression checks

```sh
python3 -m unittest discover -s tests -p test_presentation_bundle.py -v
python3 -m unittest discover -s tests -p test_bundle_sources.py -v
python3 -m unittest discover -s tests -p test_distribution.py -v
```

These use synthetic files and disposable directories, with no downloads or
provider calls. Run a real build after changing the build recipe or dependency
lock, and run native verification on Apple Silicon before distributing it.
