# Infographic Studio

This is the independently runnable feasibility and foundations increment.
It saves local briefs and serves protected project APIs. Story generation,
image providers, the editing desk, final approval, exports, and installers are
tracked in the [roadmap](https://github.com/dbbaskette/marketing-studio/issues/136).
Do not treat the foundation page or renderer spike as a complete infographic tool.

Python 3.11 or newer and Git are required. Application code uses the standard
library and has no frontend build step. Run from this source folder:

```sh
python3 runner/studio.py status
python3 runner/studio.py setup --workspace /path/to/an/empty/local/workspace
python3 runner/studio.py create "Working title" --direction suggest --preset a4
python3 runner/studio.py serve --open
```

Status does not initialize anything. Setup and launch are explicit actions;
they preserve a configured workspace and never install software or call a provider.
Use `INFOGRAPHIC_STUDIO_DATA` to select a separate application-data folder and
`STUDIOS_CONFIG` to select disposable shared settings during testing. Shared
settings remain authoritative; this increment only reads their workspace choice.
Team repository connection is deferred rather than silently replaced with local
storage. Existing populated folders cannot be repurposed by setup.

`serve` binds loopback and keeps session keys in the browser fragment. Its piped
status line never includes a key. The initial page is informational; create/edit
briefs through the native CLI until the editing desk lands.

Run offline checks with a supported Python interpreter:

```sh
python3 -m unittest discover -s tests -v
```

Tests generate synthetic content in disposable folders, not this repository, and
never call providers or use personal settings. The optional graphics smoke command
requires an explicitly named installed headless Chromium executable; it never
downloads a browser. See [renderer selection](docs/rendering-decision.md),
[provider feasibility](docs/provider-capabilities.md), and [saved contracts](docs/contracts.md).
