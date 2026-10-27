"""The Studio Runner: a program that takes a deck from a form to its delivery, stopping
where the deck's review level says for a decision on the page.

Each module's own docstring says what a caller needs to know.

Kept once for Presentation Studio and Training Studio, in the shared runner,
core/studio_core/shared_runner (reached here as studio_core.shared_runner, through the
scripts folder's studio_core link). Each of these runner/<name>.py is a facade that
passes the product in, so `runner.<name>` is the shared module made for this studio:

    companion      finding a companion skill, and running any command so that Stop and a
                   time limit end everything it started
    agents         starting the person's own agent as a confined worker for one job
    brand          the person's own brand skill, whichever it is
    brand_source   the brand skill's own repository: its releases, and installing one
    research       the harness-research command line
    documents      documents and pasted text a person supplies for a deck
    team           sharing a workspace with teammates: who drives a deck, notifications,
                   what is published, and a deck's folder brought in
    gitstate       the workspace: one folder, inside a git repository, where the decks
                   and their state live

Partly shared: the common part of each lives in core/studio_core/shared_runner/<name>.py
and is bound into this studio's module with studio_core.modules.bind; the rest is this
studio's own:

    settings       what this computer remembers: the default agent and the limits
    setup          setting this computer up: the workspace, a new deck's defaults, the
                   limits and how previews are rendered
    slides         the harness-slides command line
    worker_tools   the only tools a worker has, and the server that offers them
    upkeep         whether Presentation Studio and the skills it uses are in place and
                   current
    page           the runner's server: the page, with the engine behind it

This studio's own, among them:

    engine         takes each deck through its steps, and what the page shows of it
    studio         the `studio` command: serve, status and saved-work
    decks          a deck's folder and its run record
    stages         the deck pipeline as data: which steps a deck has, and where it stands
    jobs           one job for one worker, the tries at each step, and what a run record
                   holds of them
    research_steps research for a deck, from its plan to the report the person decides on
    steps          the steps a deck goes through, one module per family of stages

The core's modules sit beside this package, in skills/presentation-studio/scripts:

    workspace      the refusal a person reads (WorkspaceError) and safe writes
    home           what belongs to this computer: the data folder, JSON files, the decks
                   it remembers
    hub            a team hub: a git repository of published decks, joined and synced
    sync_guidance  fetching, pinning and verifying the guidance a deck follows
    computer       whether this computer has what a deck needs
    gdrive         Google Drive through gcloud: a Google Doc read as text

Refusals meant for a person are raised as the core's WorkspaceError, with a sentence to
show as it is.

Importing this package puts the core on the import path, so `import workspace` and
`import home` work anywhere in the runner. The core is found in either layout: in a
checkout of the repository it is skills/presentation-studio/scripts, and in an installed
version it is the scripts folder beside this package.
"""
import sys
from pathlib import Path

_ABOVE = Path(__file__).resolve().parent.parent
CORE = next((place for place in (_ABOVE / 'skills' / 'presentation-studio' / 'scripts',
                                 _ABOVE / 'scripts')
             if (place / 'workspace.py').is_file()), _ABOVE / 'scripts')
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))
