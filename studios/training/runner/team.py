"""Training Studio's team: the shared runner's, for this studio
(core/studio_core/shared_runner/team.py)."""
import sys

import runner  # noqa: F401  puts the core on the import path
from studio_core.shared_runner.team import for_product

sys.modules[__name__] = for_product(__name__, 'Training Studio',
                                    ITEM='training', NOTIFY='TRAINING_STUDIO_NOTIFY',
                                    TAG_UNDER_TOOL=True, REVISION_MARK='')
