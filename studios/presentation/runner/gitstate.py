"""Presentation Studio's gitstate: the shared runner's, for this studio
(core/studio_core/shared_runner/gitstate.py), with this studio's folder, words and README."""
import sys

import runner  # noqa: F401  puts the core on the import path
import studios_config
from studio_core.shared_runner.gitstate import for_product

README = """# Presentations

This folder holds decks made with Presentation Studio, one folder each. Each step that
was kept and each decision a person made is a commit, so the history says what happened.

- Open a deck's folder to read its slides, sources notes and other files.
- `hub.json` tells Presentation Studio that this folder is its own. Leave it where it is.
- Working files, saved sources and lock files stay on each person's computer. The ignore
  file here keeps them out.

Change a deck through Presentation Studio, not by hand, so its record stays true.
"""

sys.modules[__name__] = for_product(
    __name__, 'Presentation Studio', TOOL='presentation-studio', FOLDER='presentations',
    ITEM='deck', ITEMS='decks', README=README, studios_config=studios_config,
    REQUIRE_WORKSPACE_MARKER=True)
