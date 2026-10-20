"""Each studio offers a way back to the Marketing Studio tab that opened it.

Marketing Studio adds its own address to the link of a studio it opens. The studio accepts
it only for the same scheme and host on another port, and then shows a link that targets
the Marketing Studio tab by name.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

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

    def test_marketing_studio_names_itself_in_studio_links(self):
        text = HOME.read_text()
        self.assertIn("if (!standalone) window.name = 'marketing-studio';", text)
        source = 'const location = {origin: "http://127.0.0.1:8790"};\n' + function(text, 'withHome')
        found = self.evaluate(source, '[withHome("http://127.0.0.1:8791/#token=abc"), '
                                      'withHome("http://127.0.0.1:8792/#abc")]')
        self.assertEqual(found, ['http://127.0.0.1:8791/#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790',
                                 'http://127.0.0.1:8792/#abc&home=http%3A%2F%2F127.0.0.1%3A8790'])

    def test_studio_pages_hold_a_hidden_link_back(self):
        for folder in STUDIOS:
            with self.subTest(studio=folder.relative_to(ROOT).as_posix()):
                self.assertIn(LINK, (folder / 'index.html').read_text())


if __name__ == '__main__':
    unittest.main()
