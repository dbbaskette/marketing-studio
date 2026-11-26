"""Blog Studio's gitstate: the shared runner's, for this studio
(core/studio_core/shared_runner/gitstate.py), with this studio's folder, words and README.

Blog Studio passes its own ways where they differ from the shared ones: its ignore file;
a remembered workspace that keeps only its name, clone and folder, with the branch and the
repository read from the folder's hub.json (`support.place`); when to share written to the
shared settings every time it is asked (`support.keep_share`), and never by setting up, so
a guarded join can prepare a workspace without remembering it; and, as the lock a sync
holds by default, Blog Studio's own repository lock (`support.sync_lock`), which takes the
shared settings lock first and lets in a caller that already holds it.
"""

import sys

import studios_config
from studio_core.shared_runner import whole_module

from . import support

README = """# Blogs

This folder holds blogs made with Blog Studio, one folder each. Each step that
was kept and each decision a person made is a commit, so the history says what happened.

- Open a blog's folder to read its research, outline, draft and other files.
- `hub.json` tells Blog Studio that this folder is its own. Leave it where it is.
- Working files, saved sources and lock files stay on each person's computer. The ignore
  file here keeps them out.

Change a blog through Blog Studio, not by hand, so its record stays true.
"""

IGNORED = (
    '/.uploads/',
    '/.desk-imports/',
    '/.library/',
    '/.curation.json',
    '**/.google-native/',
    '**/.google-*.json',
    '/.google-*/',
    '/.google-*.json',
    '/.harness-*/',
    '/.source-analysis.json',
    '/.active-article.json',
    '/.blog-runner.lock',
    '/work/',
    '/sources/',
    '/.blog-runs/',
    '/.blog-run-settings.json',
    '/.studio.lock',
    '/.team-sync.json',
    '/.desk-receipts/',
    '/.derived-cache/',
    '/.google-staging/',
    '/.blog-settings.json',
    '/.active-article',
    '**/session.local.json',
    '**/history/google-*-native.json',
    '**/history/google-*-accepted.json',
    '**/.harness-research/guidance/',
    '**/.harness-slides/guidance/',
    '*.lock',
    '**/.blog-studio/lock',
)

sys.modules[__name__] = whole_module(
    'gitstate',
    __name__,
    'Blog Studio',
    TOOL='blog-studio',
    FOLDER='blogs',
    ITEM='blog',
    ITEMS='blogs',
    README=README,
    IGNORED=IGNORED,
    studios_config=studios_config,
    REMEMBERED=('name', 'repo', 'folder'),
    PLACE=support.place,
    KEEP_SHARE=support.keep_share,
    SET_UP_KEEPS_SHARE=False,
    HELD=support.sync_lock,
    SYNC_LOCKS=(),
    MODULES={'home': support, 'hub': support, 'sync_guidance': support, 'workspace': support},
)
