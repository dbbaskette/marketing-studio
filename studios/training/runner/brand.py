"""Training Studio's brand: the shared runner's, for this studio
(core/studio_core/shared_runner/brand.py). Its pins are this studio's installer's."""
import sys
from pathlib import Path

import runner  # puts the core on the import path
from studio_core.shared_runner.brand import for_product

sys.modules[__name__] = for_product(
    __name__, 'Training Studio',
    PINS=Path(runner.__file__).resolve().parents[1] / 'installer' / 'companions.json')
