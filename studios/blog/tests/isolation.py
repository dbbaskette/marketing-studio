"""Keep every test off this computer's own home folder, studio settings and Blog Studio data.

Every test file imports this first, before any Blog Studio module, because some of them read
these locations when they load. Without it a test reads the person's real studios config;
when that names an assistant, adding a source starts a real analysis job with that assistant.
The home folder is a temporary one too: an installer run without --home writes its log under
~/.local/state, and other defaults (~/blogs, ~/.codex) live there as well.
A test that wants shared settings writes them to os.environ['STUDIOS_CONFIG'].
"""

import atexit
import os
from pathlib import Path
import shutil
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'blog-studio' / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

PLACE = tempfile.mkdtemp(prefix='blog-studio-tests-')
atexit.register(shutil.rmtree, PLACE, ignore_errors=True)
(Path(PLACE) / 'home').mkdir()
os.environ['HOME'] = str(Path(PLACE) / 'home')
os.environ['STUDIOS_CONFIG'] = str(Path(PLACE) / 'config' / 'studios-config.json')
os.environ['STUDIOS_LIBRARY'] = str(Path(PLACE) / 'library')   # the shared Document Library
os.environ['BLOG_STUDIO_DATA'] = str(Path(PLACE) / 'data')


def voices_on(root):
    """Turn on the older voice tools for a disposable workspace, as the hidden switch in
    Blog Studio settings does: the tests of voice learning, Write as and the default voice
    run with it on. Only a workspace a test made is ever written."""
    import json

    root = Path(root).resolve()
    if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise RuntimeError('Turn the switch on only in a disposable workspace.')
    path = root / '.blog-run-settings.json'
    saved = json.loads(path.read_text()) if path.is_file() else {'schema': 1, 'defaults': {}}
    saved['features'] = {**saved.get('features', {}), 'voice': True}
    path.write_text(json.dumps(saved, indent=2) + '\n')
