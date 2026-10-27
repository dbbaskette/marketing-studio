"""Presentation Studio's documents: the shared runner's, for this studio
(core/studio_core/shared_runner/documents.py). A deck's folder holds its run record."""
import sys

import runner  # noqa: F401  puts the core on the import path
from runner.decks import RUN
from studio_core.shared_runner.documents import for_product

sys.modules[__name__] = for_product(__name__, 'Presentation Studio', ITEM='deck',
                                    IS_ITEM=lambda root: (root / RUN).is_file())
