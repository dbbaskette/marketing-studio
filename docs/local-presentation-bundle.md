# Rebuild the local Presentation Studio bundle

The build recipe lives in the repository. Generated ZIPs, download caches and
Tanzu Brand assets stay local. The first target is **Apple Silicon, macOS 13+**;
you can build and verify its archive on an Intel Mac. Native execution and
account access still need testing on the destination Mac.

From the Marketing Studio checkout, using Python 3.11+ and Node.js 22+ with npm
and Git available:

```sh
python3 scripts/build_presentation_bundle.py
```

If your system Python is older, an existing uv installation can select Python:

```sh
uv run --python 3.14 python scripts/build_presentation_bundle.py
```

The default brand source is the sibling `../tanzu-brand` project. Override it
or the output location explicitly when needed:

```sh
python3 scripts/build_presentation_bundle.py \
  --brand /path/to/tanzu-brand \
  --output "$HOME/LocalBundles/presentation-studio"
```

The output defaults to `~/LocalBundles/presentation-studio/`; its `cache/`
directory retains verified downloads. `--cache /path/to/cache` changes that
location. Generated paths inside the checkout are permitted only under the
existing ignored `build/` and `dist/` directories. The builder never installs
anything into your real HOME, starts a studio, or runs a provider job. Building
may download dependencies; installing the completed bundle uses its local files.

A successful build writes a versioned ZIP and a SHA-256 sidecar. The filename
includes the Presentation Studio version, Tanzu Brand version, platform and
content ID. Existing builds are retained; the same inputs reproduce the same
archive. Failed downloads or verification leave earlier archives intact.

## After updating components

- **Presentation Studio and shared Marketing Studio code:** rerun the builder.
  It snapshots the current checkout, including local source edits. Git revision,
  modified status and payload hashes are recorded without absolute source paths.
- **Tanzu Brand:** update the source project and rerun. Its official release
  packer selects and verifies the distributable assets; no installed skill,
  credentials, workspace or arbitrary project files are copied.
- **Harness Slides and Harness Research:** update `pins/companions.json`, then
  rerun. To resolve the newest stable releases allowed by the existing requirements:

  ```sh
  python3 scripts/update_companions.py --check
  python3 scripts/update_companions.py
  python3 scripts/build_presentation_bundle.py
  ```

- **Private Python and Node:** update the exact URLs, versions and SHA-256 values
  in `pins/runtimes.json`, then rerun. Cross-platform slide dependencies must
  remain pure JavaScript, as enforced by the existing release preparation code.
- **LibreOffice, Google Cloud CLI, Codex and preview tools:** update
  `pins/presentation-bundle.json`, then rerun. Every archive and conda package has
  an immutable HTTPS URL and SHA-256. Keep the Codex wrapper/native versions
  aligned. When updating Poppler or Git, replace the complete resolved
  `osx-arm64`/`noarch` dependency closure, not only the top-level package. For a
  private trial lock, use `--tools-lock /path/to/lock.json`.

The Google Cloud CLI lock explicitly omits two dangling certificate links in
gsutil's upstream test fixtures. Runtime files and licenses are retained; other
broken or escaping archive links still fail the build.

The builder does not silently upgrade components. Review and test changes to
locks before distributing a new bundle. A cached download is rechecked on every
build; remove a corrupt cached file and rerun to download it again.

## Inspect and verify

```sh
python3 scripts/build_presentation_bundle.py --plan
python3 scripts/build_presentation_bundle.py --verify /path/to/bundle.zip
```

`--plan` prints versions, sources and paths without downloads or writes. Archive
verification streams every file through its SHA-256 and rejects unsafe paths,
links, duplicate names, missing entries and unexpected files. ZIP permissions
preserve the installation launcher. Packaging does not certify native ARM
execution or live services.

On the destination Mac, extract the ZIP and open **Install Presentation Studio.command**.
Then use `~/Applications/Verify Presentation Studio.command` for offline tool,
brand, PowerPoint, PDF and PNG checks. The verification uses disposable output
and account directories. **Open Presentation Studio Tools.command** opens a
terminal with the private tools for destination sign-in.

The bundle includes Presentation Studio, the Marketing Studio launcher/setup,
Harness Slides, Harness Research, Tanzu Brand, private Python/Node/Codex,
LibreOffice, Poppler/Git and their native dependencies, Google Cloud CLI, and
Harness Slides' standard Gemini API image tools. Arial comes from macOS or your
licensed installation. Claude Code, the legacy unofficial Gemini browser route,
and browser-based brand development audits use separate optional setup.
Google permissions, assistant sign-in, image API keys and billing belong to the
destination account. No credentials or personal content are packaged.

## Regression checks

```sh
python3 -m unittest discover -s tests -p test_presentation_bundle.py -v
python3 -m unittest discover -s tests -p test_distribution.py -v
```

These use synthetic files and disposable directories, with no downloads or
provider calls. Run a real build after changing the build recipe or dependency
lock, and run native verification on Apple Silicon before distributing it.
