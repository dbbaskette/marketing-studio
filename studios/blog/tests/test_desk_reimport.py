"""A desk blog edited outside the desk: a chat save, a restore from history, or Google's
accepted text comes onto the desk as a new version of each part it changed, so the next desk
save keeps it. No assistant, Google account or provider write."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
from pathlib import Path
import secrets
import tempfile
import unittest

import desk
import google_workflow as google
import management
import studio

DRAFT = '# T\n\nOpening.\n\n## A\n\nTeh text.\n\n## B\n\nBee.\n'
FIXED = '# T\n\nOpening.\n\n## A\n\nThe text.\n\n## B\n\nBee.\n'


class ReimportCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='desk-reimport-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / 'work'
        studio.initialize(self.root)
        self.number = 0

    def file(self, body, suffix='.md'):
        self.number += 1
        path = self.base / (str(self.number) + suffix)
        path.write_text(body if isinstance(body, str) else json.dumps(body))
        return str(path)

    def run_command(self, *words):
        args = studio.parser().parse_args(['--root', str(self.root), *words])
        with studio.locked(self.root):
            if args.group == 'google':
                return google.command(self.root, args)
            return getattr(studio, args.group + '_command')(self.root, args)

    def desk_blog(self, manuscript=DRAFT):
        made = management.dispatch(
            self.root,
            'desk-create',
            {'operation': secrets.token_hex(16), 'title': 'T', 'manuscript': manuscript},
        )
        return made['id']

    def view(self, ident):
        return management.view(self.root, 'desk', {'id': [ident]})

    def folder(self, ident):
        return studio.inside(self.root, 'articles', ident)

    def save_on_desk(self, ident, text='T2'):
        shown = self.view(ident)
        management.dispatch(
            self.root,
            'desk-save',
            {
                'id': ident,
                'seen': shown['revision'],
                'part': 'title',
                'text': text,
                'session': 'a' * 16,
            },
        )


class ChatSaveTests(ReimportCase):
    def test_a_chat_save_comes_onto_the_desk_and_a_later_desk_save_keeps_it(self):
        ident = self.desk_blog()
        before = self.view(ident)
        first = before['sections'][0]['id']
        result = self.run_command(
            'article',
            'save',
            '--id',
            ident,
            '--kind',
            'draft',
            '--file',
            self.file(FIXED),
            '--label',
            'proofread',
        )
        self.assertTrue(result['saved_artifact']['reopened'])
        shown = self.view(ident)
        self.assertEqual(shown['sections'][0]['id'], first, 'the section keeps its id')
        self.assertEqual(shown['sections'][0]['text'], 'The text.')
        self.assertEqual(shown['revision'], before['revision'] + 1)
        kept = desk.versions(self.root, ident, first)
        self.assertEqual((kept[0]['source'], kept[0]['text']), ('chat', 'Teh text.'))
        self.assertEqual(desk.versions(self.root, ident, shown['sections'][1]['id']), [])
        self.assertEqual((self.folder(ident) / 'DRAFT.md').read_text(), FIXED)
        # An open desk page that saw the old text cannot type over the changed section.
        with self.assertRaisesRegex(ValueError, 'changed since you opened it'):
            management.dispatch(
                self.root,
                'desk-save',
                {
                    'id': ident,
                    'seen': before['revision'],
                    'part': first,
                    'text': 'Old.',
                    'session': 'c' * 16,
                },
            )
        self.save_on_desk(ident)
        self.assertIn('The text.', (self.folder(ident) / 'DRAFT.md').read_text())
        self.assertEqual(self.view(ident)['title'], 'T2')

    def test_sections_are_matched_by_heading_then_place_and_a_dropped_one_can_come_back(self):
        ident = self.desk_blog()
        before = self.view(ident)
        a, b = (section['id'] for section in before['sections'])
        edited = '# T\n\nOpening.\n\n## B\n\nBee, moved first.\n\n## New\n\nAdded.\n'
        self.run_command(
            'article', 'save', '--id', ident, '--kind', 'draft', '--file', self.file(edited)
        )
        shown = self.view(ident)
        self.assertEqual([s['heading'] for s in shown['sections']], ['B', 'New'])
        self.assertEqual(shown['sections'][0]['id'], b, 'B keeps its id by heading')
        self.assertNotIn(shown['sections'][1]['id'], (a, b))
        self.assertEqual([item['heading'] for item in desk.removed(self.root, ident)], ['A'])

    def test_an_unchanged_save_changes_nothing(self):
        ident = self.desk_blog()
        before = self.view(ident)
        self.run_command(
            'article', 'save', '--id', ident, '--kind', 'draft', '--file', self.file(DRAFT)
        )
        self.assertEqual(self.view(ident)['revision'], before['revision'])


class RestoreTests(ReimportCase):
    def test_a_restore_from_history_comes_onto_the_desk(self):
        ident = self.desk_blog()
        history = self.folder(ident) / 'history'
        history.mkdir(exist_ok=True)
        (history / 'draft-20260101T000000000000-abcdef12.md').write_text(FIXED)
        preview = self.run_command(
            'article',
            'restore',
            '--id',
            ident,
            '--revision',
            'draft-20260101T000000000000-abcdef12.md',
        )
        self.run_command(
            'article',
            'restore',
            '--id',
            ident,
            '--revision',
            'draft-20260101T000000000000-abcdef12.md',
            '--expected',
            preview['expected'],
            '--apply',
        )
        shown = self.view(ident)
        self.assertEqual(shown['sections'][0]['text'], 'The text.')
        self.assertEqual(
            desk.versions(self.root, ident, shown['sections'][0]['id'])[0]['source'], 'chat'
        )
        self.save_on_desk(ident)
        self.assertIn('The text.', (self.folder(ident) / 'DRAFT.md').read_text())


class GoogleTests(ReimportCase):
    def obs(self, body, **changes):
        observation = {
            'schema': 1,
            'document_id': 'fixture-doc',
            'url': 'https://docs.google.com/document/d/fixture-doc/edit?tab=t.0',
            'tab_ids': ['t.0'],
            'revision_id': 'revision-1',
            'observed_at': '2026-10-01T12:00:00+00:00',
            'content_sha256': studio.digest(body.encode()),
            'suggestions': 'excluded',
            'structure_verified': True,
            'folder_id': 'folder-1',
        }
        observation.update(changes)
        return ['--observation', self.file(observation, '.json'), '--file', self.file(body)]

    def test_accepted_google_text_comes_onto_the_desk(self):
        ident = self.desk_blog()
        body = (self.folder(ident) / 'DRAFT.md').read_text()
        prepared = self.run_command('google', 'prepare', '--id', ident)
        self.run_command(
            'google', 'confirm', '--id', ident, '--transfer', prepared['transfer'], *self.obs(body)
        )
        inputs = self.obs(FIXED, revision_id='revision-2')
        comparison = self.run_command('google', 'compare', '--id', ident, *inputs)
        self.assertEqual(comparison['status'], 'remote-only')
        self.run_command(
            'google',
            'accept',
            '--id',
            ident,
            *inputs,
            '--expected-comparison',
            comparison['comparison'],
        )
        shown = self.view(ident)
        self.assertEqual(shown['sections'][0]['text'], 'The text.')
        self.assertEqual(
            desk.versions(self.root, ident, shown['sections'][0]['id'])[0]['source'], 'google'
        )
        _, record = studio.item(self.root, 'articles', ident)
        self.assertEqual(record['artifact_hashes']['draft'], studio.digest(FIXED.encode()))
        self.save_on_desk(ident)
        self.assertIn('The text.', (self.folder(ident) / 'DRAFT.md').read_text())


class ImageReimportTests(ReimportCase):
    def test_a_chat_save_or_googles_text_with_images_keeps_them_beside_the_text(self):
        from test_desk import DEFINITIONS, GOOGLE, IMAGE_ONE, OPENING

        ident = self.desk_blog(GOOGLE)
        edited = GOOGLE.replace('The end.', 'The end, from chat.')
        self.run_command(
            'article', 'save', '--id', ident, '--kind', 'draft', '--file', self.file(edited)
        )
        shown = self.view(ident)
        self.assertEqual(shown['opening'], OPENING.replace('The end.', 'The end, from chat.'))
        self.assertNotIn('data:image', json.dumps(shown))
        self.assertEqual((self.folder(ident) / 'DRAFT.md').read_text(), edited)
        # Text that names the images without their definitions keeps the images it had.
        bare = '# Images synthetic\n\n' + OPENING.replace('The end.', 'Bare.') + '\n'
        with studio.locked(self.root):
            draft = desk.reimport(self.root, ident, bare, 'google')
        self.assertEqual(draft['images']['image1']['uri'], IMAGE_ONE)
        self.assertTrue(
            (self.folder(ident) / 'DRAFT.md').read_text().endswith('Bare.\n\n' + DEFINITIONS + '\n')
        )
        kept = desk.versions(self.root, ident, 'opening')
        self.assertNotIn('data:image', json.dumps(kept))


if __name__ == '__main__':
    unittest.main()
