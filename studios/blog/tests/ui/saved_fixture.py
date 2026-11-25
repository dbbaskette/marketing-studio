"""Disposable Blog Studio with saved step-by-step blogs, for looking at their saved records.

Serves the real page over a synthetic workspace, synthetic settings and no providers. It loads
static saved-flow fixtures (tests/saved_fixtures.py): a saved run with unstructured outline
notes, which opens on the desk; a finished run, which keeps its Done card; a run whose step
was left queued, which waits for Stop; and a saved blog whose run record cannot be read,
which is read-only. Prints the private address and the blogs' IDs; stops with the process.

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
from test_blog_runner import RunnerCase  # noqa: E402

case = RunnerCase('runTest')
httpd = None
try:
    case.setUp()
    moves = saved_fixtures.load(case.root, 'unstructured-outline')
    finished = saved_fixtures.load(case.root, 'finished-page')
    waits = saved_fixtures.load(case.root, 'draft-gate-queued')
    unread = saved_fixtures.load(case.root, 'draft-gate-chat')
    (case.root / 'articles' / unread / 'derived/blog-run.json').write_text('{not json')
    studios_config.update({'local': {'root': str(case.root)}})
    preferences.finish(studios_config, lambda _: None)
    httpd, url = management.server(case.root, shared_setup=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(
        json.dumps(
            {'url': url, 'moves': moves, 'finished': finished, 'waits': waits, 'read_only': unread}
        ),
        flush=True,
    )
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    signal.signal(signal.SIGINT, lambda *_: done.set())
    done.wait()
finally:
    if httpd:
        httpd.shutdown()
        httpd.server_close()
    case.doCleanups()
