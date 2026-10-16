# Marketing Studio

Set up the tools once, then open Blog Studio, Presentation Studio, or Training
Studio from one local home page. Each studio also works with its own launcher.

Marketing Studio holds shared settings and launches the studios. It does not
replace their writing, research, slide, or training workflows.

## Open Marketing Studio

You need Python 3.11 or newer and Git. Install whichever studios you want to use:

- [Blog Studio](https://github.com/dbbaskette/blog-studio)
- [Presentation Studio](https://github.com/dbbaskette/presentation-studio)
- [Training Studio](https://github.com/dbbaskette/training-studio)

Clone this repository, then double-click **Open Marketing Studio.command** on
macOS, or run:

```sh
git clone https://github.com/dbbaskette/marketing-studio.git
cd marketing-studio
python3 -m marketing_studio --open
```

Leave the terminal open while working. Press Ctrl-C to stop Marketing Studio and
the studio processes it started. Independently opened studios keep running.

The first visit opens setup. Choose your name and assistant, where work lives,
and optionally a brand skill and delivery format. Existing shared values appear
in the form. Each step saves, so you can leave and return without starting over.
Finishing setup prepares installed studios without starting an assistant job.
Later visits open the studio launch page. Change shared choices in **Shared
settings** and inspect installed tools in **This computer**.

## Your work can stay local

**Local Git on this computer** is the default. A remote is optional. Each studio
keeps a separate repository inside your work folder, including its normal
content subfolder:

```text
Studios/
  blog-workspace/blogs/
  presentation-workspace/presentations/
  training-workspace/trainings/
```

Git needs your name and email before it can record decisions. If Git asks for
those, configure them with `git config --global user.name "Your Name"` and
`git config --global user.email "you@example.com"`.

For collaboration, choose an existing repository address and branch instead.
Finishing setup creates a separate clone for each unconfigured studio. It never
creates or changes a remote repository's visibility. The studios use their normal
sharing rules. Existing workspaces are kept; a changed default never moves work.

## One set of settings

Shared values live in `~/.config/studios-config.json`, the same file the studios
already read. This includes your name, assistant, model ID and reasoning, work
location, brand skill source and identity, delivery format, and sharing choice.
An assistant's default model is used when the model field is blank. Enter only a
model ID available to your signed-in CLI. Presentation Studio and Training Studio
consume the shared model and reasoning settings; current Blog Studio versions use
the selected CLI's configured model. Per-job overrides and studio-specific limits
remain in each studio.

The file contains preferences, never authentication tokens. Sign-in stays with
Git, your assistant, and Google. Changes merge under the same lock the studios
use; an outdated form cannot overwrite another studio's conflicting edit.

Finishing setup stores each installed studio's native workspace settings too.
Opening it with its own launcher afterward uses that workspace. A studio
installed later is prepared when you first open it from Marketing Studio.

Marketing Studio finds sibling source checkouts and installations under
`~/.local/share/<studio-name>/current`. Set another installation folder under
**Shared settings → Studio installations**. An installation folder contains
`runner/studio.py` for Presentation Studio and Training Studio, or
`scripts/start_studio.py` (also supported under `skills/blog-studio/`) for Blog
Studio. No source checkout is modified.

## Development and verification

No Python packages or frontend build are required. Node.js is needed for the
JavaScript syntax check, and by studios that use companion skills.

```sh
bash scripts/ci/check.sh
# On the configured development Mac, using the shared disposable VM runner:
bash scripts/ci/tart-macos.sh --dry-run
bash scripts/ci/tart-macos.sh
# Optional acceptance against sibling source checkouts, using disposable data:
python3 scripts/ci/native_acceptance.py
# Or check the installed runtimes:
python3 scripts/ci/native_acceptance.py --installed
```

See [architecture](docs/architecture.md), [test instructions](docs/testing.md),
and [source provenance](docs/provenance.md). Earlier design proposals in `docs/`
are historical proposals; the architecture document describes the implementation.
