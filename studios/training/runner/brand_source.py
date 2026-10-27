"""Training Studio's brand_source: the shared runner's, for this studio
(core/studio_core/shared_runner/brand_source.py)."""
import sys

import runner  # noqa: F401  puts the core on the import path
from studio_core.shared_runner.brand_source import for_product

sys.modules[__name__] = for_product(__name__, 'Training Studio')
