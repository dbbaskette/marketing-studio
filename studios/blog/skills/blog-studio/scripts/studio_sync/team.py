"""Blog Studio's team: the shared runner's, for this studio
(core/studio_core/shared_runner/team.py).

Blog Studio has no `runner` package, and its own `hub` module is the Team Hub registry, so
it passes the modules the shared code names: `studio_sync.support` holds its Git
primitives, its data folder and its refusal, and `studio_sync.gitstate` is its workspace.
A published revision is `blog-studio/<folder>/<id>/<number>`, and `BLOG_STUDIO_NOTIFY`
names the program that shows a notification.
"""

import sys

from studio_core.shared_runner import whole_module

from . import gitstate, support

sys.modules[__name__] = whole_module(
    'team',
    __name__,
    'Blog Studio',
    ITEM='blog',
    NOTIFY='BLOG_STUDIO_NOTIFY',
    TAG_UNDER_TOOL=True,
    REVISION_MARK='',
    MODULES={'home': support, 'hub': support, 'workspace': support, 'gitstate': gitstate},
)
