"""Exercise one studio's actual source route in an isolated process; never launch authors."""
import base64
import json
from pathlib import Path
import sys
from unittest import mock
from pdf_fixture import source_pdf

ROOT = Path(__file__).resolve().parents[1]
product = sys.argv[1]
sys.path.insert(0, str(ROOT / 'studios' / product / 'tests'))
if product in ('training', 'presentation'):
    from test_runner_page import PageCase
    case = PageCase()
    case.setUp()
    post = lambda sent: case.post('research-sources', sent)
elif product == 'blog':
    from test_desk import RouteCase
    case = RouteCase()
    case.setUp()
    post = lambda sent: case.post('research-sources', sent)
else:
    from helpers import Isolated
    from runner.server import Page
    from runner.workspace import Store
    case = Isolated()
    case.setUp()
    page = Page(8765, Store.setup(case.workspace))
    post = lambda sent: json.loads(page.write('/api/research-sources', sent)[2])
try:
    from studio_core import source_documents
    value = post({'action': 'create'})
    value = post({'action': 'capture', 'id': value['id'], 'expected': value['revision'],
        'kind': 'file', 'name': 'source.PDF', 'content': base64.b64encode(source_pdf()).decode()})
    assert value['sources'][0]['status'] == 'ready', value['sources']
    preview = post({'action': 'preview', 'id': value['id'], 'source': value['sources'][0]['id']})
    assert 'Synthetic PDF source for all studios.' in preview['text'], preview
    with mock.patch.object(source_documents.shutil, 'which', return_value=None):
        value = post({'action': 'capture', 'id': value['id'], 'expected': value['revision'],
            'kind': 'file', 'name': 'reader-missing.pdf', 'content': base64.b64encode(source_pdf()).decode()})
    assert value['sources'][0]['status'] == 'ready'
    assert value['sources'][1]['status'] == 'needs-attention'
    assert 'pdftotext' in value['sources'][1]['problem']
    print('PASS '+product+': actual PDF upload/extraction/preview; missing reader is explicit and retained peers survive')
finally:
    case.doCleanups()
