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
import management
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


class EnforcementCase(SwitchCase):
    def setUp(self):
        super().setUp()
        guide = self.base / 'VOICE.md'
        guide.write_text('Short direct sentences.')
        args = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'profile',
                'create',
                '--name',
                'Avery',
                '--guide-file',
                str(guide),
                '--status',
                'confirmed',
            ]
        )
        self.profile = studio.profile_command(self.root, args)

    def refused(self, route, data):
        before = sorted(str(p) for p in self.root.rglob('*') if p.is_file())
        with self.assertRaisesRegex(ValueError, OFF):
            management.dispatch(self.root, route, data)
        after = sorted(str(p) for p in self.root.rglob('*') if p.is_file())
        self.assertEqual(before, after, route + ' wrote something while refused')

    def reaches(self, route, data):
        """Not refused by the switch: it succeeds, or stops at its own check."""
        try:
            return management.dispatch(self.root, route, data)
        except Exception as error:  # noqa: BLE001 - any refusal but the switch's
            self.assertNotIn(OFF, str(error), route)
            return None

    def on(self):
        isolation.voices_on(self.root)


class EnforcementTests(EnforcementCase):
    ROUTES = (
        ('voice-links-preview', {'text': 'https://example.com/a', 'author': 'Avery'}),
        ('voice-links-import', {'text': 'https://example.com/a', 'author': 'Avery'}),
        ('library-voices', {'operation': 'a' * 32, 'authors': ['Avery'], 'confirmed': True}),
        ('library-add-samples', {'operation': 'a' * 32}),
        ('library-author-same', {'author': 'A. Avery', 'into': 'Avery', 'expected': 'x'}),
        ('library-author-different', {'author': 'A. Avery', 'others': ['Avery']}),
        ('library-selection', {'action': 'voice-learn', 'ids': ['x']}),
        (
            'tool-action',
            {'action': 'job-create', 'kind': 'voice-learn', 'operation': 'b' * 32},
        ),
        (
            'tool-action',
            {'action': 'job-create', 'kind': 'voice-audition', 'operation': 'c' * 32},
        ),
        ('tool-action', {'action': 'voice-apply', 'id': 'none', 'profile': 'none'}),
        ('tool-action', {'action': 'source-purpose', 'source': 'x', 'purpose': 'voice-sample'}),
        (
            'tool-action',
            {
                'action': 'interview-start',
                'title': 'T',
                'audience': 'A',
                'goal': 'G',
                'profile': 'avery',
                'operation': 'd' * 32,
            },
        ),
        (
            'upload',
            {
                'operation': 'e' * 32,
                'filename': 'a.md',
                'content': 'SGk=',
                'purpose': 'voice-sample',
            },
        ),
        (
            'upload',
            {
                'operation': 'f' * 32,
                'purpose': 'voice-sample',
                'files': [{'filename': 'a.md', 'content': 'SGk='}],
            },
        ),
        (
            'upload',
            {
                'operation': 'a1' * 16,
                'purpose': 'author-background',
                'files': [{'linkedin': {'filename': 'export.zip', 'content': 'SGk='}}],
            },
        ),
        (
            'upload',
            {
                'operation': 'a2' * 16,
                'filename': 'about.md',
                'content': 'SGk=',
                'purpose': 'author-background',
            },
        ),
        (
            'upload',
            {
                'operation': 'a3' * 16,
                'purpose': 'author-background',
                'files': [{'filename': 'about.md', 'content': 'SGk='}],
            },
        ),
    )

    def test_author_suggestions_are_refused_while_off(self):
        with self.assertRaisesRegex(ValueError, OFF):
            management.view(self.root, 'library-authors', {})
        self.on()
        self.assertIn('authors', management.view(self.root, 'library-authors', {}))

    def test_each_old_voice_route_is_refused_while_off_and_reached_when_on(self):
        for route, data in self.ROUTES:
            with self.subTest(route=route, data=data):
                self.refused(route, data)
        self.on()
        for route, data in self.ROUTES:
            with self.subTest(route=route, data=data):
                self.reaches(route, data)

    def test_examples_of_a_kind_of_post_are_not_voices(self):
        found = management.dispatch(
            self.root,
            'voice-links-preview',
            {'text': 'https://example.com/a', 'author': 'Announcements', 'purpose': 'style-sample'},
        )
        self.assertEqual(found['purpose'], 'style-sample')
        self.reaches('library-selection', {'action': 'style-learn', 'ids': ['x']})
        self.reaches(
            'tool-action', {'action': 'source-purpose', 'source': 'x', 'purpose': 'style-sample'}
        )
        self.reaches(
            'upload',
            {
                'operation': '9' * 32,
                'filename': 'a.md',
                'content': 'SGk=',
                'purpose': 'style-sample',
            },
        )

    def test_a_default_voice_in_settings_is_refused_unless_the_same_save_turns_it_on(self):
        shown = blog_runner.settings(self.root)
        pin = {'profile_id': self.profile['id'], 'revision': 1}
        with self.assertRaisesRegex(ValueError, OFF):
            management.dispatch(
                self.root,
                'run-settings',
                {**shown['defaults'], 'voice': pin, 'voice_before': None},
            )
        self.assertIsNone(blog_runner.settings(self.root)['voice'])
        saved = management.dispatch(
            self.root,
            'run-settings',
            {
                **shown['defaults'],
                'voice': pin,
                'voice_before': None,
                'features': {'voice': True},
                'features_before': {'voice': False},
            },
        )
        self.assertEqual(saved['voice'], pin)

    def test_a_voice_job_queued_before_the_switch_went_off_is_not_saved(self):
        import tool_jobs

        self.on()
        for kind in ('voice-learn', 'voice-audition'):
            job = tool_jobs.create(
                self.root,
                ('a' if kind == 'voice-learn' else 'b') * 32,
                kind,
                {},
                'g',
                'basis',
                {'name': 'X'},
            )
            saved = tool_jobs.read(self.root, job['id'])
            saved.update(status='ready', result={'content': 'A guide.', 'notes': ''})
            tool_jobs.write(self.root, saved)
        blog_runner.settings(
            self.root, self.form(features={'voice': False}, features_before={'voice': True})
        )
        for kind in ('voice-learn', 'voice-audition'):
            with self.subTest(kind=kind):
                self.assertRaisesRegex(
                    ValueError,
                    OFF,
                    management.dispatch,
                    self.root,
                    'tool-action',
                    {
                        'action': 'job-apply',
                        'job': ('a' if kind == 'voice-learn' else 'b') * 32,
                        'content': 'A guide.',
                    },
                )

    def test_a_guide_saved_by_hand_takes_no_voice_samples_while_off(self):
        data = {
            'action': 'profile-save',
            'name': 'Plain',
            'guide': 'Plain.',
            'status': 'confirmed',
            'confirmed': True,
        }
        self.refused('tool-action', {**data, 'samples': ['some-source']})
        self.assertTrue(management.dispatch(self.root, 'tool-action', {**data, 'samples': []}))


class ToneWhileOffTests(EnforcementCase):
    def setUp(self):
        super().setUp()
        import writing_defaults

        writing_defaults.set_personal(
            self.root, 'voice', {'profile_id': self.profile['id'], 'revision': 1}
        )

    def create(self):
        return blog_runner.create(
            self.root,
            {'title': 'T', 'audience': 'A', 'goal': 'G', 'research': 'none', 'tone': 'Warm'},
        )

    def test_a_new_run_writes_with_tone_and_no_default_voice(self):
        found = self.create()
        _, record = studio.item(self.root, 'articles', found['id'])
        self.assertEqual(record['voice'], {'mode': 'tone', 'tone': 'Warm'})
        self.assertIsNone(blog_runner.options(self.root)['default_voice'])

    def test_with_the_switch_on_the_default_voice_applies_as_before(self):
        self.on()
        found = self.create()
        _, record = studio.item(self.root, 'articles', found['id'])
        self.assertEqual(record['voice']['mode'], 'profile')
        self.assertEqual(record['voice']['profile_id'], self.profile['id'])
        self.assertEqual(
            blog_runner.options(self.root)['default_voice']['profile'], self.profile['id']
        )

    def test_turning_it_off_leaves_saved_voices_and_pins_alone(self):
        self.on()
        found = self.create()
        folder = studio.inside(self.root, 'articles', found['id'])
        pinned = (folder / 'session.json').read_bytes()
        profiles = sorted(
            p.read_bytes() for p in studio.inside(self.root, 'profiles').rglob('*') if p.is_file()
        )
        blog_runner.settings(
            self.root,
            self.form(features={'voice': False}, features_before={'voice': True}),
        )
        self.assertEqual((folder / 'session.json').read_bytes(), pinned)
        self.assertEqual(
            sorted(
                p.read_bytes()
                for p in studio.inside(self.root, 'profiles').rglob('*')
                if p.is_file()
            ),
            profiles,
        )
        self.assertEqual(
            blog_runner.engine(self.root).describe(found['id'])['voice_profile'], self.profile['id']
        )

    def test_an_old_run_still_writes_in_its_pinned_voice_while_off(self):
        self.on()
        found = blog_runner.create(
            self.root,
            {
                'title': 'T',
                'audience': 'A',
                'goal': 'G',
                'research': 'none',
                'profile': self.profile['id'],
            },
            'page',
        )
        blog_runner.settings(
            self.root, self.form(features={'voice': False}, features_before={'voice': True})
        )
        sent = []

        def worker(*args, **kwargs):
            sent.append(args[1])
            return {'content': '# Synthetic outline', 'notes': 'Fake worker only.'}

        engine = blog_runner.Engine(self.root, worker=worker)
        self.addCleanup(engine.close)
        engine.keep_local(found['id'], {'enabled': True})
        engine.once(found['id'])
        self.assertEqual(sent[0]['voice']['mode'], 'profile')
        self.assertEqual(sent[0]['voice']['guide'], 'Short direct sentences.')

    def test_a_chat_article_writes_no_default_voice_while_off(self):
        args = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'article',
                'create',
                '--title',
                'Chat',
                '--mode',
                'first-draft',
            ]
        )
        record = studio.article_command(self.root, args)
        self.assertNotEqual(record['voice']['mode'], 'profile')

    def test_a_desk_blog_is_tone_only(self):
        import desk
        import desk_jobs

        with studio.locked(self.root):
            made = desk.create(
                self.root, {'title': 'Desk', 'manuscript': '## A\n\nText.', 'tone': 'Plain'}
            )
            _, record = studio.item(self.root, 'articles', made['id'])
            self.assertEqual(record['voice'], {'mode': 'tone', 'tone': 'Plain'})
            extra, _ = desk_jobs._context(self.root, desk.read(self.root, made['id']))
        self.assertNotIn('voice', extra)


if __name__ == '__main__':
    unittest.main()
