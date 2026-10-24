"""Every file a studio page loads must be allowed through the trusted-network gateway.

A page that works on this computer but is missing a script on a phone fails with an error
such as "Can't find variable: sDeskBegin": the gateway in marketing_studio/network.py lets
only the listed page files through.
"""
import re
import unittest

from marketing_studio import network
from test_ui_consistency import APP_PAGES, ROOT

LOADED = re.compile(r'<(?:script|link)\b[^>]*\b(?:src|href)="(?!https?:|//|data:)/?([^"#?]+)"')


class GatewayStaticTests(unittest.TestCase):
    def test_every_file_a_page_loads_passes_the_gateway(self):
        for page in APP_PAGES:
            with self.subTest(page=page.relative_to(ROOT).as_posix()):
                loaded = {'/' + path for path in LOADED.findall(page.read_text())}
                self.assertTrue(loaded)
                self.assertEqual(sorted(loaded - network.STATIC), [])


if __name__ == '__main__':
    unittest.main()
