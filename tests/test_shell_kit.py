"""The shell kit every studio page shows: its shared appearance setting, the script each
page loads, and the styles its parts are drawn with. Disposable settings only."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import marketing_studio  # noqa: F401  puts the core on the import path
from studio_core import preferences, server, studios_config

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('core/studio_core/setup_web/index.html',
         'studios/blog/skills/blog-studio/assets/management/index.html',
         'studios/presentation/skills/presentation-studio/scripts/desk/index.html',
         'studios/training/skills/training-studio/scripts/desk/index.html',
         'studios/infographic/runner/web/index.html')


class AppearanceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        named = mock.patch.dict(os.environ, {
            'STUDIOS_CONFIG': str(Path(folder.name) / 'studios-config.json')})
        named.start()
        self.addCleanup(named.stop)

    def test_an_appearance_is_light_dark_or_this_computers_own(self):
        for chosen in ('light', 'dark', None):
            self.assertEqual(preferences.check({'appearance': chosen}, {}).get('appearance'),
                             chosen)
        for wrong in ('sepia', '', 3):
            with self.assertRaises(ValueError):
                preferences.check({'appearance': wrong}, {})

    def test_a_saved_appearance_keeps_every_other_value_and_refuses_an_outdated_form(self):
        studios_config.update({'person': {'name': 'Alex'}, 'share': 'asked'})
        seen = studios_config.read()[0]
        preferences.save(studios_config, {'appearance': 'dark'}, seen)
        self.assertEqual(studios_config.read()[0],
                         {**seen, 'appearance': 'dark'})
        # Another page chose differently meanwhile: nothing is written over it.
        with self.assertRaises(preferences.Conflict) as refused:
            preferences.save(studios_config, {'appearance': 'light'}, seen)
        self.assertEqual(refused.exception.fields, ['appearance'])
        self.assertIn('“Appearance”', str(refused.exception))
        preferences.save(studios_config, {'appearance': None}, studios_config.read()[0])
        self.assertIsNone(studios_config.read()[0]['appearance'])

    def test_a_page_is_served_already_looking_as_chosen(self):
        page = b'<html><body data-product="Blog Studio"><main></main></body></html>'
        self.assertEqual(server.with_appearance(page), page, 'nothing saved: nothing said')
        studios_config.update({'appearance': 'dark'})
        self.assertEqual(server.with_appearance(page), page.replace(
            b'<body', b'<body data-appearance="dark"'))
        self.assertEqual(server.with_appearance(b'<bodyguard>'), b'<bodyguard>')
        Path(os.environ['STUDIOS_CONFIG']).write_text('{not json')
        self.assertEqual(server.with_appearance(page), page, 'an unreadable file changes nothing')


class LoadedTests(unittest.TestCase):
    def test_every_page_loads_the_kit_before_its_own_script(self):
        for name in PAGES:
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn('shell.js" defer></script>', text, name)
            self.assertLess(text.index('shell.js'), text.index('app.js'), name)

    def test_every_server_serves_it(self):
        self.assertIn('/shell.js', server.DECK_PAGES)
        self.assertTrue(Path(server.DECK_PAGES['/shell.js'][0]).is_file())
        from marketing_studio import network
        self.assertIn('/shell.js', network.STATIC, 'and the phone bridge passes it on')
        blog = (ROOT / 'studios/blog/skills/blog-studio/scripts/management.py').read_text()
        self.assertIn("'/shell.js': (", blog)

    def test_the_kit_draws_only_with_shared_tokens_and_respects_reduced_motion(self):
        styles = (ROOT / 'ui-kit/style.css').read_text(encoding='utf-8')
        kit = styles[styles.index('/* The shell kit ('):]
        for part in ('.track-stage[data-state="yours"]', '.shell-palette-row[aria-selected="true"]',
                     '.appearance-switch', '.finish-card', '.track-compact'):
            self.assertIn(part, kit)
        reduced = ''.join(block.split('}\n}')[0] for block
                          in kit.split('@media (prefers-reduced-motion: reduce)')[1:])
        for moving in ('.track-stage[data-state="yours"] .track-mark', '.finish-card', '.finish-seal',
                       '.workbench-pulse', '.move-card', '[data-making="true"]'):
            self.assertIn(moving, reduced)
        for part in ('.workbench-pulse[data-state="working"]', '.move-card', '[data-zone="work"]',
                     '[data-zone="rail"]', '.workbench-head'):
            self.assertIn(part, kit)
        script = (ROOT / 'core/studio_core/deck_web/shell.js').read_text(encoding='utf-8')
        for name in ('connect', 'commands', 'palette', 'track', 'finish', 'setAppearance', 'arc', 'pulse', 'move'):
            self.assertRegex(script, rf'\b{name}\b')
        self.assertNotIn('localStorage', script, 'a page address changes with each launch')


if __name__ == '__main__':
    unittest.main()
