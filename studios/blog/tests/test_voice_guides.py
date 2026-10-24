"""Voice guides: a name and text, written by hand or made from a few samples, saved as the
profiles voices always were. They work whether or not the older voice tools are on."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import base64
import json
import unittest

import article_tools
import blog_runner
import management
import studio
import tool_jobs
from test_voice_switch import SwitchCase

SAMPLE = 'We ship small changes often. Each one says what it fixes, and nothing more.'


class GuideCase(SwitchCase):
    def samples(self, count=3):
        return [{'text': SAMPLE + ' Sample %d.' % number} for number in range(count)]

    def make(self, **extra):
        data = {
            'action': 'job-create',
            'kind': 'voice-guide',
            'operation': 'a' * 32,
            'name': 'Plain release notes',
            'samples': self.samples(),
            **extra,
        }
        return management.dispatch(self.root, 'tool-action', data)

    def learned(self, name='Avery', status='provisional'):
        guide = self.base / 'VOICE.md'
        guide.write_text('# Avery\n\nShort direct sentences, with one dry joke per post.\n')
        args = studio.parser().parse_args(
            ['--root', str(self.root), 'profile', 'create', '--name', name]
            + ['--guide-file', str(guide), '--status', status]
        )
        return studio.profile_command(self.root, args)

    def listed(self):
        return management.view(self.root, 'voice-guides', {})


class ListTests(GuideCase):
    def test_existing_learned_voices_are_listed_as_guides(self):
        made = self.learned()
        found = self.listed()
        self.assertEqual(
            found['guides'],
            [
                {
                    'id': made['id'],
                    'name': 'Avery',
                    'revision': 1,
                    'status': 'provisional',
                    'says': 'Short direct sentences, with one dry joke per post.',
                }
            ],
        )
        self.assertFalse(studio.voices_on(self.root), 'guides do not need the switch')

    def test_a_retired_guide_is_listed_last_and_a_long_line_is_cut(self):
        retired = self.learned('Old voice')
        article_tools.retire_profile(
            self.root,
            {
                'profile': retired['id'],
                'expected': article_tools.profile(self.root, retired['id'])['expected'],
                'confirmed': True,
            },
        )
        with studio.locked(self.root):
            article_tools.save_profile(
                self.root,
                {'name': 'Long', 'guide': 'word ' * 100, 'status': 'confirmed', 'confirmed': True},
            )
        found = self.listed()['guides']
        self.assertEqual([g['name'] for g in found], ['Long', 'Old voice'])
        self.assertLessEqual(len(found[0]['says']), 161)
        self.assertTrue(found[0]['says'].endswith('…'))


class WriteTests(GuideCase):
    def test_a_guide_written_by_hand_is_a_confirmed_profile_without_samples(self):
        saved = management.dispatch(
            self.root,
            'tool-action',
            {
                'action': 'profile-save',
                'name': 'Plain',
                'guide': 'Plain words. Short paragraphs.',
                'status': 'confirmed',
                'confirmed': True,
            },
        )
        found = article_tools.profile(self.root, saved['profile'])
        self.assertEqual((found['status'], found['sample_ids']), ('confirmed', []))
        self.assertEqual(found['guide'], 'Plain words. Short paragraphs.')
        self.assertTrue(studio.inside(self.root, 'profiles', saved['profile']).is_dir())

    def test_retire_keeps_the_guide_on_disk(self):
        made = self.learned()
        expected = article_tools.profile(self.root, made['id'])['expected']
        management.dispatch(
            self.root,
            'tool-action',
            {
                'action': 'profile-retire',
                'profile': made['id'],
                'expected': expected,
                'confirmed': True,
            },
        )
        self.assertEqual(article_tools.profile(self.root, made['id'])['status'], 'retired')
        self.assertTrue((studio.inside(self.root, 'profiles', made['id']) / 'VOICE.md').is_file())


class MakeTests(GuideCase):
    def test_three_to_twenty_samples(self):
        for count in (2, 21):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, '3 to 20'):
                self.make(samples=self.samples(count), operation=str(count) * 32)
        with self.assertRaisesRegex(ValueError, 'Sample 3 has no text'):
            self.make(samples=[*self.samples(2), {'text': '  '}])
        with self.assertRaisesRegex(ValueError, 'Name the voice guide'):
            self.make(name='')

    def test_the_job_reads_the_samples_and_no_author_library_or_audition(self):
        job = tool_jobs.read(self.root, self.make()['id'])
        self.assertEqual(job['kind'], 'voice-guide')
        self.assertEqual(job['payload']['name'], 'Plain release notes')
        self.assertEqual(
            [s['title'] for s in job['payload']['samples']], ['Sample 1', 'Sample 2', 'Sample 3']
        )
        self.assertNotIn('author', json.dumps(job['payload']))
        self.assertIn('Voice profile capability', job['guidance'])
        self.assertIn('no audition', job['guidance'])
        self.assertIn('Do not say who wrote', job['guidance'])
        self.assertEqual(job['metadata'], {'name': 'Plain release notes', 'samples': 3})
        self.assertEqual(list(studio.inside(self.root, 'sources').glob('*')), [])

    def test_an_uploaded_sample_is_read_as_text_and_an_unreadable_one_is_named(self):
        upload = {
            'filename': 'notes.md',
            'content': base64.b64encode(('# Notes\n\n' + SAMPLE).encode()).decode(),
        }
        job = tool_jobs.read(self.root, self.make(samples=[*self.samples(2), upload])['id'])
        self.assertEqual(job['payload']['samples'][2]['title'], 'notes.md')
        self.assertIn(SAMPLE, job['payload']['samples'][2]['text'])
        empty = {'filename': 'empty.txt', 'content': base64.b64encode(b'   ').decode()}
        with self.assertRaisesRegex(ValueError, 'empty.txt has no readable text'):
            self.make(samples=[*self.samples(2), empty], operation='b' * 32)
        with self.assertRaisesRegex(ValueError, 'Markdown, text, HTML, DOCX or PDF'):
            self.make(
                samples=[*self.samples(2), {'filename': 'a.exe', 'content': 'SGk='}],
                operation='c' * 32,
            )

    def test_a_ready_guide_is_read_edited_and_saved_as_a_guide(self):
        made = self.make()

        def worker(engine, payload, guidance, **options):
            return {'content': '# Plain release notes\n\nShort and specific.', 'notes': ''}

        tool_jobs.once(blog_runner.Engine(self.root, worker=worker))
        shown = management.view(self.root, 'tool-job', {'job': [made['id']]})
        self.assertEqual(shown['status'], 'ready')
        self.assertFalse(shown['source_changed'])
        self.assertEqual(self.listed()['making'][0]['id'], made['id'])
        saved = management.dispatch(
            self.root,
            'tool-action',
            {
                'action': 'job-apply',
                'job': made['id'],
                'name': 'Release notes',
                'content': '# Release notes\n\nShort, specific, edited.',
            },
        )
        found = article_tools.profile(self.root, saved['profile'])
        self.assertEqual((found['name'], found['status']), ('Release notes', 'confirmed'))
        self.assertIn('edited', found['guide'])
        self.assertEqual(self.listed()['making'], [])
        self.assertEqual([g['name'] for g in self.listed()['guides']], ['Release notes'])

    def test_only_guide_jobs_are_read_and_a_failed_one_can_be_discarded(self):
        made = self.make()
        stray = tool_jobs.create(
            self.root, 'e' * 32, 'voice-guide', {}, 'g', 'b', {'name': 'Stray'}
        )
        self.assertEqual([row['id'] for row in self.listed()['making']], [made['id']])
        self.assertNotIn(stray['id'], json.dumps(self.listed()))
        saved = tool_jobs.read(self.root, made['id'])
        saved.update(status='failed', error='Synthetic failure.')
        tool_jobs.write(self.root, saved)
        self.assertEqual(self.listed()['making'][0]['status'], 'failed')
        management.dispatch(
            self.root, 'tool-action', {'action': 'guide-discard', 'job': made['id']}
        )
        self.assertEqual(self.listed()['making'], [])
        with self.assertRaisesRegex(ValueError, 'not a voice guide being made'):
            management.dispatch(
                self.root, 'tool-action', {'action': 'guide-discard', 'job': stray['id']}
            )


if __name__ == '__main__':
    unittest.main()
