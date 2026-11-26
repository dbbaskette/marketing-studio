"""Blog Studio's brand source: the shared runner's brand_source, for this studio
(core/studio_core/shared_runner/brand_source.py).

The brand skill's repository is reached with Blog Studio's own Git primitives
(`studio_sync.support`, which keeps hooks off), and its address is checked by Blog Studio's
own wrapper of the shared settings check (`studio_brand.settings`).
"""

import sys

from studio_core.shared_runner import whole_module
from studio_sync import support

from . import companion, settings

sys.modules[__name__] = whole_module(
    'brand_source',
    __name__,
    'Blog Studio',
    MODULES={'hub': support, 'workspace': support, 'companion': companion, 'settings': settings},
)
