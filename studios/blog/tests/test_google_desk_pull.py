"""Linked desk CLI pulls use synthetic Google reads and never write to Google."""

import isolation  # noqa: F401
import secrets
import unittest
from unittest.mock import patch

import desk
import desk_finish
import google_reconcile
import google_workflow
import management
import studio
import test_google_intake as intake


class DeskGooglePullTests(unittest.TestCase):
    setUp = intake.GoogleIntakeTests.setUp
    preview = intake.GoogleIntakeTests.preview
    start = intake.GoogleIntakeTests.start

    def linked_desk(self):
        imported = self.start(self.preview())
        made = management.dispatch(
            self.root,
            'desk-create',
            {'operation': secrets.token_hex(16), 'article': imported['id']},
        )
        return made['id']

    def pull(self, ident, preview=None, resolution=None):
        words = ['google', 'pull', '--id', ident]
        if preview:
            words += [
                '--accept',
                preview['preview'],
                '--expected',
                preview['expected'],
                '--comparison',
                preview['comparison'],
                '--confirmed',
            ]
        if resolution is not None:
            file = self.base / 'reviewed-resolution.md'
            file.write_text(resolution)
            words += ['--resolution-file', str(file)]
        args = studio.parser().parse_args(['--root', str(self.root), *words])
        with studio.locked(self.root):
            return google_workflow.command(self.root, args)

    def offer(self, ident):
        draft = desk.read(self.root, ident)
        section = draft['sections'][0]
        with studio.locked(self.root):
            return desk_finish.keep(
                self.root,
                ident,
                secrets.token_hex(16),
                'finish-humanize',
                [
                    {
                        'part': section['id'],
                        'before': section['text'],
                        'after': 'A proposed local revision.',
                        'note': 'Synthetic suggestion.',
                    }
                ],
            )

    def test_pull_keeps_local_edits_and_imports_remote_renamed_section_with_history(self):
        ident = self.linked_desk()
        before = desk.read(self.root, ident)
        with studio.locked(self.root):
            desk.save(self.root, ident, before['revision'], 'title', 'Local title')
        for block in self.client.doc['tabs'][0]['documentTab']['body']['content']:
            for element in block.get('paragraph', {}).get('elements', []):
                run = element['textRun']
                run['content'] = (
                    run['content'].replace('handoffs', 'handover').replace('slow', 'fast')
                )
        self.client.doc['revisionId'] = 'r2'
        self.client.version = '2'
        found = self.pull(ident)
        self.assertIn('Local title', found['local'])
        self.assertIn('handover', found['remote'])
        self.assertFalse(found['google_written'])
        with self.assertRaisesRegex(ValueError, 'Both versions changed'):
            self.pull(ident, found)
        resolution = found['local'].replace('handoffs', 'handover').replace('slow', 'fast')
        accepted = self.pull(ident, found, resolution)
        self.assertEqual(accepted['status'], 'accepted')
        after = desk.read(self.root, ident)
        self.assertEqual(after['title'], 'Local title')
        self.assertIn('handover', after['sections'][0]['heading'])
        self.assertIn('fast', after['sections'][0]['text'])
        history = desk.versions(self.root, ident, before['sections'][0]['id'])
        self.assertTrue(any(row['source'] == 'google' for row in history))
        self.assertEqual(self.client.writes, 0)

    def test_changed_desk_revision_refuses_accept_without_replacing_local_work(self):
        ident = self.linked_desk()
        found = self.pull(ident)
        before = desk.read(self.root, ident)
        with studio.locked(self.root):
            desk.save(self.root, ident, before['revision'], 'title', 'Keep this local title')
        with self.assertRaisesRegex(ValueError, 'desk changed'):
            self.pull(ident, found)
        self.assertEqual(desk.read(self.root, ident)['title'], 'Keep this local title')
        self.assertEqual(self.client.writes, 0)

    def test_pending_suggestions_are_previewed_and_block_accept(self):
        ident = self.linked_desk()
        self.offer(ident)
        found = self.pull(ident)
        self.assertTrue(found['has_proposals'])
        with self.assertRaisesRegex(ValueError, 'saved wording suggestions'):
            self.pull(ident, found)
        self.assertEqual(len(google_reconcile.read(self.root, ident)['proposals']), 1)
        self.assertEqual(self.client.writes, 0)

    def test_new_suggestion_invalidates_an_earlier_comparison(self):
        ident = self.linked_desk()
        found = self.pull(ident)
        self.offer(ident)
        with self.assertRaisesRegex(ValueError, 'desk changed'):
            self.pull(ident, found)
        self.assertEqual(self.client.writes, 0)

    def test_active_desk_job_refuses_preview_before_google_read(self):
        ident = self.linked_desk()
        with (
            patch('desk_jobs.jobs', return_value=[{'status': 'running'}]),
            patch('desk_jobs.busy', return_value=True),
            patch('google_roundtrip.capture') as capture,
        ):
            with self.assertRaisesRegex(ValueError, 'already working'):
                self.pull(ident)
        capture.assert_not_called()


if __name__ == '__main__':
    unittest.main()
