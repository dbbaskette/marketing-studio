"""Each studio offers a way back to the Marketing Studio tab that opened it.

Marketing Studio adds its own address to the link of a studio it opens. The studio accepts
it only for the same scheme and host on another port, and then shows a link that targets
the Marketing Studio tab by name. A phone cannot bring another tab forward, so there Marketing
Studio opens the studio in its own tab and says so (back=tab); the way back then leaves in that
same tab, where Marketing Studio still holds its key.

A studio page can also be reached without that link: an old tab, a bookmark, a link from the
terminal. Marketing Studio therefore tells each studio it starts the port of its home page, the
studio's server names that port on its HTML page, and the page builds the way back from it on
its own host.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import marketing_studio  # noqa: F401  (puts the shared core on the path)
from studio_core.server import for_product as server_for, suite_port, with_suite_port

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'core/studio_core/setup_web/app.js'
STUDIOS = (
    ROOT / 'studios/blog/skills/blog-studio/assets/management',
    ROOT / 'studios/presentation/skills/presentation-studio/scripts/desk',
    ROOT / 'studios/training/skills/training-studio/scripts/desk',
)
HERE = {'protocol': 'http:', 'hostname': '127.0.0.1', 'port': '8791'}
CASES = [
    ('#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790', 'http://127.0.0.1:8790'),
    ('#abc&home=http%3A%2F%2F127.0.0.1%3A8790', 'http://127.0.0.1:8790'),
    ('#token=abc', ''),
    ('', ''),
    ('#token=abc&home=http%3A%2F%2Felsewhere.example%3A8790', ''),
    ('#token=abc&home=https%3A%2F%2F127.0.0.1%3A8790', ''),
    ('#token=abc&home=http%3A%2F%2F127.0.0.1%3A8791', ''),
    ('#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790%2Fapi', ''),
    ('#token=abc&home=javascript%3Aalert(1)', ''),
    ('#token=abc&home=http%3A%2F%2F127.0.0.1%3A99999', ''),
]
# The port Marketing Studio names on a studio's page, and the way back each one gives.
PORTS = [
    ('8790', 'http://127.0.0.1:8790'),
    ('65535', 'http://127.0.0.1:65535'),
    ('8791', ''),
    ('0', ''),
    ('65536', ''),
    ('99999', ''),
    ('08790', ''),
    ('-1', ''),
    ('87 90', ''),
    ('8790/api', ''),
    ('abc', ''),
    ('', ''),
    (None, ''),
]
LINK = ('<a id="go-suite" class="nav-item suite-link" target="marketing-studio" hidden>'
        '<span class="nav-label">Marketing Studio</span></a>')


def function(source: str, name: str) -> str:
    found = re.search(r'function ' + name + r'\([^)]*\) \{[\s\S]*?\n\}', source)
    if not found:
        raise AssertionError(name + ' is not defined as a top-level function')
    return found.group(0)


@unittest.skipUnless(shutil.which('node'), 'needs Node.js')
class SuiteLinkTests(unittest.TestCase):
    def evaluate(self, source: str, expression: str):
        done = subprocess.run(['node', '-e', source + '\nprocess.stdout.write(JSON.stringify('
                               + expression + '));'], capture_output=True, text=True, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_studios_accept_only_marketing_studio_on_the_same_host(self):
        for folder in STUDIOS:
            with self.subTest(studio=folder.relative_to(ROOT).as_posix()):
                source = function((folder / 'app.js').read_text(), 'suiteHome')
                found = self.evaluate(source, json.dumps([hash for hash, _ in CASES])
                                      + '.map((hash) => suiteHome(hash, ' + json.dumps(HERE) + '))')
                self.assertEqual(found, [wanted for _, wanted in CASES])

    def test_studios_find_marketing_studio_by_the_port_their_page_names(self):
        lan = {'protocol': 'http:', 'hostname': '192.168.1.20', 'port': '51234'}
        for folder in STUDIOS:
            with self.subTest(studio=folder.relative_to(ROOT).as_posix()):
                text = (folder / 'app.js').read_text()
                source = function(text, 'suiteHome') + '\n' + function(text, 'suitePort')
                found = self.evaluate(source, json.dumps([port for port, _ in PORTS])
                                      + '.map((port) => suitePort(port, ' + json.dumps(HERE) + '))')
                self.assertEqual(found, [wanted for _, wanted in PORTS])
                # On the private network the home page shares this page's host as well.
                self.assertEqual(self.evaluate(source, 'suitePort("8790", ' + json.dumps(lan) + ')'),
                                 'http://192.168.1.20:8790')
                # The link's own address comes first, then the page's port, then the tab's memory.
                wiring = text[text.index('suiteHome(', text.index('function suitePort(') + 1):]
                wiring = wiring[:wiring.index("sessionStorage.getItem('marketing-studio-home')")]
                self.assertIn('suitePort(document.body?.dataset?.suitePort, ', wiring)

    def test_marketing_studio_names_itself_in_studio_links(self):
        text = HOME.read_text()
        self.assertIn("if (!standalone) window.name = 'marketing-studio';", text)
        source = 'const location = {origin: "http://127.0.0.1:8790"};\n' + function(text, 'withHome')
        found = self.evaluate(source, '[withHome("http://127.0.0.1:8791/#token=abc"), '
                                      'withHome("http://127.0.0.1:8792/#abc")]')
        self.assertEqual(found, ['http://127.0.0.1:8791/#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790',
                                 'http://127.0.0.1:8792/#abc&home=http%3A%2F%2F127.0.0.1%3A8790'])

    def test_a_phone_opens_a_studio_in_the_same_tab_and_says_so(self):
        text = HOME.read_text()
        source = 'const location = {origin: "http://127.0.0.1:8790"};\n' + function(text, 'withHome')
        found = self.evaluate(source, '[withHome("http://127.0.0.1:8791/#token=abc", true), '
                                      'withHome("http://127.0.0.1:8791/#token=abc", false)]')
        self.assertEqual(found, ['http://127.0.0.1:8791/#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790&back=tab',
                                 'http://127.0.0.1:8791/#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790'])
        chosen = self.evaluate(function(text, 'inThisTab'), json.dumps([
            ['(pointer: coarse)'], ['(max-width: 52rem)'], [], ['(hover: hover)']])
            + '.map((matching) => inThisTab((query) => matching.some((m) => query.includes(m))))')
        self.assertEqual(chosen, [True, True, False, False])
        self.assertIn('if (inThisTab(', text)

    def test_studios_leave_in_the_same_tab_when_opened_in_it(self):
        hashes = ['#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790&back=tab',
                  '#abc&home=http%3A%2F%2F127.0.0.1%3A8790&back=tab',
                  '#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790', '#token=abc&back=other', '']
        for folder in STUDIOS:
            with self.subTest(studio=folder.relative_to(ROOT).as_posix()):
                source = (folder / 'app.js').read_text()
                found = self.evaluate(function(source, 'suiteBack'),
                                      json.dumps(hashes) + '.map((hash) => suiteBack(hash))')
                self.assertEqual(found, [True, True, False, False, False])
                wiring = (folder / 'app.js').read_text() + (folder / 'runner.js').read_text() \
                    if (folder / 'runner.js').exists() else source
                self.assertIn("removeAttribute('target')", wiring)
                self.assertIn('marketing-studio-back', wiring)

    def test_a_new_link_in_an_open_tab_is_used(self):
        text = HOME.read_text()
        found = self.evaluate(function(text, 'linkKey'), json.dumps([
            ['#token=abc', False], ['#token=abc&view=settings', False], ['#abc', True],
            ['#abc', False], ['', False], ['#home=x', True]])
            + '.map(([hash, bare]) => linkKey(hash, bare))')
        self.assertEqual(found, ['abc', 'abc', 'abc', '', '', ''])
        self.assertIn("window.addEventListener('hashchange'", text)
        self.assertIn("window.addEventListener('hashchange'", (STUDIOS[0] / 'runner.js').read_text())

    def test_studio_pages_hold_a_hidden_link_back(self):
        for folder in STUDIOS:
            with self.subTest(studio=folder.relative_to(ROOT).as_posix()):
                self.assertIn(LINK, (folder / 'index.html').read_text())


class SuitePortTests(unittest.TestCase):
    """A studio Marketing Studio started names the home page's port on its page, and only then."""

    def test_only_a_valid_port_is_taken(self):
        for value, wanted in (('8790', 8790), ('1', 1), ('65535', 65535), ('0', None), ('65536', None),
                              ('123456', None), ('-1', None), (' 8790', None), ('8790\n', None),
                              ('\u0663', None), ('abc', None), ('', None)):
            with self.subTest(value=value):
                self.assertEqual(suite_port({'MARKETING_STUDIO_HOME_PORT': value}), wanted)
        self.assertIsNone(suite_port({}))

    def test_the_port_goes_on_the_body_only(self):
        page = b'<!doctype html><html><body data-product="Training Studio"><p>x</p></body></html>'
        self.assertEqual(with_suite_port(page, 8790), page.replace(
            b'<body data-product', b'<body data-suite-port="8790" data-product'))
        self.assertEqual(with_suite_port(b'<body>', 8790), b'<body data-suite-port="8790">')
        self.assertEqual(with_suite_port(page, None), page)
        self.assertEqual(with_suite_port(b'<bodyguard>', 8790), b'<bodyguard>')
        self.assertEqual(with_suite_port(b'no page', 8790), b'no page')

    def test_a_studio_server_names_the_port_on_its_html_page_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            pages = Path(folder)
            (pages / 'index.html').write_text('<html><body data-product="Fixture Studio"></body></html>')
            (pages / 'app.js').write_text("document.body.dataset.suitePort;\n")
            served = server_for('_suite_port_fixture', 'Fixture Studio', 'X-Fixture-Token', pages,
                                {'/': ('index.html', 'text/html; charset=utf-8'),
                                 '/app.js': ('app.js', 'text/javascript; charset=utf-8')},
                                None, ValueError)
            page = served.Page(4321)

            class Headers(dict):
                def get_all(self, name, default=None):
                    return [self[name]] if name in self else default

            headers = Headers(Host='127.0.0.1:4321')
            for value, wanted in (('8790', True), ('0', False), ('x', False), (None, False)):
                with self.subTest(value=value):
                    environment = {key: item for key, item in os.environ.items()
                                   if key != 'MARKETING_STUDIO_HOME_PORT'}
                    if value is not None:
                        environment['MARKETING_STUDIO_HOME_PORT'] = value
                    with mock.patch.dict(os.environ, environment, clear=True):
                        html = page.answer('/', headers)[2]
                        script = page.answer('/app.js', headers)[2]
                    self.assertEqual(b'<body data-suite-port="8790" ' in html, wanted)
                    self.assertEqual(html.count(b'data-suite-port'), int(wanted))
                    self.assertEqual(script, b"document.body.dataset.suitePort;\n")


if __name__ == '__main__':
    unittest.main()
