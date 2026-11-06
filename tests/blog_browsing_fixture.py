"""Disposable native Blog Studio; no providers or personal settings."""
import json
from pathlib import Path
import signal
import sys
import threading

native = Path(__file__).resolve().parents[1] / 'studios/blog'
sys.path.insert(0, str(native / 'tests'))
from test_desk import RouteCase
import management
from studio_core import preferences, studios_config

case = RouteCase()
httpd = None
try:
    case.setUp()
    found = case.make()
    studios_config.update({'local': {'root': str(case.root)}})
    preferences.finish(studios_config, lambda _: None)
    httpd, url = management.server(case.root, shared_setup=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(json.dumps({'url': url, 'id': found['id']}), flush=True)
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    done.wait()
finally:
    if httpd:
        httpd.shutdown()
        httpd.server_close()
    case.doCleanups()
