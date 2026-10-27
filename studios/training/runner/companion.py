"""Training Studio's companion: the shared runner's, for this studio
(core/studio_core/shared_runner/companion.py)."""
import sys

import runner  # noqa: F401  puts the core on the import path
from studio_core.shared_runner.companion import for_product

sys.modules[__name__] = for_product(__name__, 'Training Studio')
