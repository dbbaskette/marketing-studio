"""The voice switch: the older voice tools are off by default, refused on the server while
off, and new blogs write with Tone. Voice guides and saved voices are not touched."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import blog_runner
import studio

OFF = 'Voices are switched off in Blog Studio settings.'


class SwitchCase(unittest.TestCase):
    """A disposable workspace and shared settings; nothing on this computer is read."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        environment = patch.dict(
            os.environ,
            {
                'BLOG_STUDIO_DATA': str(self.base / 'data'),
                'STUDIOS_CONFIG': str(self.base / 'studios-config.json'),
                'BRAND_SKILL_RUNTIME': str(self.base / 'no-brand'),
                'HARNESS_RESEARCH_RUNTIME': str(self.base / 'no-research'),
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.root = self.base / 'workspace'
        studio.initialize(self.root)
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))

    def form(self, **extra):
        shown = blog_runner.settings(self.root)
        return {**shown['defaults'], 'shared_before': shown['shared_before'], **extra}


class VoiceSwitchTests(SwitchCase):
    def test_off_by_default(self):
        self.assertEqual(blog_runner.settings(self.root)['features'], {'voice': False})
        self.assertFalse(studio.voices_on(self.root))
        with self.assertRaisesRegex(ValueError, OFF):
            studio.require_voices(self.root)

    def test_saved_with_the_form_against_what_it_showed(self):
        shown = blog_runner.settings(self.root)
        saved = blog_runner.settings(
            self.root,
            self.form(tone='Warm', features={'voice': True}, features_before=shown['features']),
        )
        self.assertEqual(saved['features'], {'voice': True})
        self.assertEqual(saved['defaults']['tone'], 'Warm')
        self.assertTrue(studio.voices_on(self.root))

    def test_a_save_without_it_keeps_the_saved_value(self):
        blog_runner.settings(
            self.root, self.form(features={'voice': True}, features_before={'voice': False})
        )
        blog_runner.settings(self.root, self.form(tone='Plain'))
        self.assertEqual(blog_runner.settings(self.root)['features'], {'voice': True})
        self.assertEqual(blog_runner.settings(self.root)['defaults']['tone'], 'Plain')

    def test_an_outdated_or_odd_form_is_refused_and_nothing_is_saved(self):
        before = blog_runner.settings(self.root)
        with self.assertRaisesRegex(ValueError, 'changed since these settings were shown'):
            blog_runner.settings(
                self.root,
                self.form(tone='New', features={'voice': True}, features_before={'voice': True}),
            )
        for bad in ({'voice': 'yes'}, {'voice': True, 'other': True}, ['voice']):
            with self.assertRaisesRegex(ValueError, 'Choose on or off'):
                blog_runner.settings(
                    self.root, self.form(tone='New', features=bad, features_before={'voice': False})
                )
        with self.assertRaisesRegex(ValueError, 'Reload the displayed settings'):
            blog_runner.settings(self.root, self.form(features={'voice': True}))
        self.assertEqual(blog_runner.settings(self.root)['defaults'], before['defaults'])
        self.assertFalse(studio.voices_on(self.root))

    def test_a_damaged_value_reads_as_off(self):
        path = studio.inside(self.root, '.blog-run-settings.json')
        for damaged in ({'voice': 'on'}, 'on', None, ['voice']):
            studio.write_json(path, {'schema': 1, 'defaults': {}, 'features': damaged})
            self.assertFalse(studio.voices_on(self.root))
        path.write_text('{not json')
        self.assertFalse(studio.voices_on(self.root))

    def test_the_test_helper_turns_it_on_for_a_disposable_workspace(self):
        isolation.voices_on(self.root)
        self.assertTrue(studio.voices_on(self.root))
        saved = json.loads(studio.inside(self.root, '.blog-run-settings.json').read_text())
        self.assertEqual(saved['features'], {'voice': True})


if __name__ == '__main__':
    unittest.main()
