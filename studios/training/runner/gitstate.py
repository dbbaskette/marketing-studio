"""Training Studio's gitstate: the shared runner's, for this studio
(core/studio_core/shared_runner/gitstate.py), with this studio's folder, words and README."""
import sys

import runner  # noqa: F401  puts the core on the import path
from runner import studios_config
from studio_core.shared_runner.gitstate import for_product

README = """# Trainings

This folder holds trainings made with Training Studio, one folder each. Each step that
was kept and each decision a person made is a commit, so the history says what happened.

- Open a training's folder to read its research, blueprint and other files.
- `hub.json` tells Training Studio that this folder is its own. Leave it where it is.
- Working files, saved sources and lock files stay on each person's computer. The ignore
  file here keeps them out.

Change a training through Training Studio, not by hand, so its record stays true.
"""

sys.modules[__name__] = for_product(
    __name__, 'Training Studio', TOOL='training-studio', FOLDER='trainings',
    ITEM='training', ITEMS='trainings', README=README, studios_config=studios_config,
    REQUIRE_WORKSPACE_MARKER=True)
