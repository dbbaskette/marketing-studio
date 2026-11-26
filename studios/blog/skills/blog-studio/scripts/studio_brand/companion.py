"""Blog Studio's companion: the shared runner's, for this studio
(core/studio_core/shared_runner/companion.py). Its refusal is Blog Studio's own
`WorkspaceError`, from `studio_sync.support`.
"""

import sys

from studio_core.shared_runner import whole_module
from studio_sync import support

sys.modules[__name__] = whole_module(
    'companion', __name__, 'Blog Studio', MODULES={'workspace': support}
)
