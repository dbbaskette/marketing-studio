"""Blog Studio's brand: the shared runner's, for this studio
(core/studio_core/shared_runner/brand.py).

A blog's brand contract is exported for the `blog` medium, with no delivery and, when one
is chosen, the author's voice profile. The brand skill's command is told only the brands
folder the shared settings name, and every question is the plain command, asked each time.
Blog Studio has no version floor (it passes no pins), and runs no readiness check or audit.
"""

import sys

from studio_core.shared_runner import whole_module
from studio_sync import support

from . import companion, source

sys.modules[__name__] = whole_module(
    'brand',
    __name__,
    'Blog Studio',
    ROOTS={},
    UNABLE='a blog cannot use a brand',
    QUICK_ASKS=False,
    MEDIUM='blog',
    TELLS_DELIVERY=False,
    DOCTOR_PROFILE=None,
    MODULES={'workspace': support, 'companion': companion, 'brand_source': source},
)
