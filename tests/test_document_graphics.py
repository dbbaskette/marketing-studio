"""Document graphics: the shared choice of who draws, and a Gemini key kept out of the config.

Every key here is synthetic, every folder disposable, and no request leaves this computer:
the transport is a stand-in.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))
from studio_core import graphics, preferences, studios_config  # noqa: E402

KEY = 'synthetic-key-0123456789abcdef'


class GraphicsCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = mock.patch.dict(os.environ, {'STUDIOS_CONFIG': str(self.root / 'shared.json')})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('GEMINI_API_KEY', None)


class KeyTests(GraphicsCase):
    def test_a_saved_key_is_private_and_never_in_the_config_or_an_answer(self):
        studios_config.update({'person': {'name': 'Author'}})
        answer = graphics.act({'key': KEY})
        self.assertEqual(answer, {'key': {'set': True, 'source': 'saved'}})
        where = graphics.key_path()
        self.assertEqual(where.parent, self.root)
        self.assertEqual(stat.S_IMODE(where.stat().st_mode), 0o600)
        self.assertEqual(graphics.key(), KEY)
        self.assertNotIn(KEY, (self.root / 'shared.json').read_text())
        self.assertNotIn(KEY, json.dumps(graphics.snapshot(studios_config.read()[0])))
        self.assertEqual(graphics.act({'clear': True}), {'key': {'set': False, 'source': None}})
        self.assertEqual(graphics.key(), '')

    def test_the_launch_environment_comes_first(self):
        graphics.save_key(KEY)
        self.assertEqual(graphics.key({'GEMINI_API_KEY': 'from-the-environment-0123456789'}),
                         'from-the-environment-0123456789')
        self.assertEqual(graphics.key_state({'GEMINI_API_KEY': 'x' * 30})['source'], 'environment')

    def test_a_key_is_not_taken_over_the_phone_link_or_when_malformed(self):
        with self.assertRaisesRegex(ValueError, 'not taken over the phone link'):
            graphics.act({'key': KEY}, remote=True)
        for bad in ('', 'short', 'has spaces in it and is long enough', None, 'x' * 300):
            with self.assertRaises(ValueError):
                graphics.act({'key': bad})
        self.assertFalse(graphics.key_path().exists())


class ModelTests(GraphicsCase):
    def transport(self, pages, seen=None):
        def answer(path, secret):
            (seen if seen is not None else []).append((path, secret))
            return pages.pop(0)
        return answer

    def test_only_picture_models_are_listed_across_pages_with_the_key_in_no_address(self):
        graphics.save_key(KEY)
        seen = []
        pages = [(200, {'models': [
            {'name': 'models/gemini-3.1-flash-image', 'displayName': 'Nano Banana 2'},
            {'name': 'models/gemini-3.1-pro', 'displayName': 'Words only'}],
            'nextPageToken': 'next'}),
            (200, {'models': [{'name': 'models/gemini-nano-banana-2.1'},
                              {'name': 'models/bad name'}]})]
        found = graphics.act({'models': 'gemini'}, transport=self.transport(pages, seen))
        self.assertIsNone(found['problem'])
        self.assertEqual([model['name'] for model in found['models']],
                         ['gemini-3.1-flash-image', 'gemini-nano-banana-2.1'])
        self.assertEqual(found['models'][0]['label'], 'Nano Banana 2 (gemini-3.1-flash-image)')
        self.assertTrue(all(KEY not in path and secret == KEY for path, secret in seen))
        self.assertIn('pageToken=next', seen[1][0])
        self.assertNotIn(KEY, json.dumps(found))

    def test_no_key_a_refused_key_and_an_unreachable_provider_each_say_so(self):
        self.assertIn('Save a Gemini API key first', graphics.act({'models': 'gemini'})['problem'])
        graphics.save_key(KEY)
        refused = graphics.act({'models': 'gemini'}, transport=self.transport([(403, {})]))
        self.assertIn('did not accept this key', refused['problem'])

        def down(path, secret):
            raise OSError('no route')
        self.assertIn('could not be reached', graphics.act({'models': 'gemini'}, transport=down)['problem'])
        self.assertEqual(graphics.act({'models': 'codex'})['models'], [])


class SettingTests(GraphicsCase):
    def test_the_choice_is_a_shared_setting_and_follows_the_assistant_until_made(self):
        self.assertEqual(graphics.chosen({'assistant': {'agent': 'codex'}})['provider'], 'codex')
        self.assertEqual(graphics.chosen({'assistant': {'agent': 'claude'}})['provider'], 'gemini')
        merged = preferences.check({'graphics': {'provider': 'gemini', 'model': 'gemini-3.1-flash-image'}},
                                   {'assistant': {'agent': 'codex'}, 'unrelated': {'keep': True}})
        self.assertEqual(merged['unrelated'], {'keep': True})
        self.assertEqual(graphics.chosen(merged), {'provider': 'gemini', 'model': 'gemini-3.1-flash-image',
                                                   'explicit': True})
        for bad in ({'provider': 'other'}, {'model': 'has space'}, {'key': KEY}):
            with self.assertRaises(ValueError):
                preferences.check({'graphics': bad}, {})


if __name__ == '__main__':
    unittest.main()
