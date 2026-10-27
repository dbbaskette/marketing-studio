"""Presentation Studio's agents: the shared runner's, for this studio
(core/studio_core/shared_runner/agents.py)."""
import sys

import runner  # noqa: F401  puts the core on the import path
from studio_core.shared_runner.agents import for_product

sys.modules[__name__] = for_product(__name__, 'Presentation Studio',
                                    DATA_VARIABLE='PRESENTATION_STUDIO_DATA')
