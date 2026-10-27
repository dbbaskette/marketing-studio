"""Training Studio's documents: the shared runner's, for this studio
(core/studio_core/shared_runner/documents.py). A training's folder holds its session."""
import sys

import runner  # noqa: F401  puts the core on the import path
import workspace
from studio_core.shared_runner.documents import for_product

sys.modules[__name__] = for_product(__name__, 'Training Studio', ITEM='training',
                                    IS_ITEM=lambda root: workspace.session_path(root).is_file())
