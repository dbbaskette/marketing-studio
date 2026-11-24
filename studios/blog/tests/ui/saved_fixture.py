"""Disposable Blog Studio with saved step-by-step blogs, for looking at their screens.

Serves the real page over a synthetic workspace, synthetic settings and no providers. It loads
static saved-flow fixtures (tests/saved_fixtures.py): a saved run with unstructured outline
notes, which Open on the desk now moves, and a saved blog whose run record cannot be read,
which opens as a read-only record. Prints the private address and the two blogs' IDs; stops
with the process.

    python3 studios/blog/tests/ui/saved_fixture.py
"""

import json
from pathlib import Path
import signal
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import isolation  # noqa: E402,F401  (first Blog Studio import: no personal settings)
import management  # noqa: E402
import saved_fixtures  # noqa: E402
from studio_core import preferences, studios_config  # noqa: E402

case = saved_fixtures.Maker('capture_only')
httpd = None
try:
    case.setUp()
    moved = saved_fixtures.load(case.root, 'unstructured-outline')
    unread = saved_fixtures.load(case.root, 'draft-gate-chat')
    (case.root / 'articles' / unread / 'derived/blog-run.json').write_text('{not json')
    studios_config.update({'local': {'root': str(case.root)}})
    preferences.finish(studios_config, lambda _: None)
    httpd, url = management.server(case.root, shared_setup=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(json.dumps({'url': url, 'moves': moved, 'read_only': unread}), flush=True)
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    signal.signal(signal.SIGINT, lambda *_: done.set())
    done.wait()
finally:
    if httpd:
        httpd.shutdown()
        httpd.server_close()
    case.doCleanups()
