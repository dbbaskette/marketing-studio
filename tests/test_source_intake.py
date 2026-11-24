"""source_intake: a folder or a spreadsheet as ordinary uploads, over disposable folders.

Every folder and workbook is synthetic and made in a temporary folder; no Google Drive
folder is read, no network is used and no assistant or provider job is started.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import marketing_studio  # noqa: F401  puts the core on the import path
from studio_core import source_intake
import xlsx_fixture

ACCEPTS = {'.md', '.txt', '.pdf', '.docx'}


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        env = mock.patch.dict(os.environ, {'HOME': str(self.base / 'home')})
        env.start()
        self.addCleanup(env.stop)
        self.folder = self.base / 'Compete'
        (self.folder / 'Battlecards').mkdir(parents=True)
        (self.folder / 'notes.md').write_text('# Notes\n\nSynthetic notes for a fictional product.\n')
        (self.folder / 'Battlecards/card.txt').write_text('A fictional battlecard.\n')
        (self.folder / 'Battlecards/Pipeline.xlsx').write_bytes(xlsx_fixture.workbook(xlsx_fixture.SAMPLE))
        (self.folder / 'picture.png').write_bytes(b'\x89PNG\r\n\x1a\nnot really')
        (self.folder / '.hidden.md').write_text('# Hidden\n')

    def test_a_local_folder_becomes_uploads_with_a_plain_report(self):
        found = source_intake.take(str(self.folder), accepts=ACCEPTS, room=10, spare=10_000_000, taken=('brief.md',))
        self.assertEqual(sorted(found['uploads']), ['Battlecards - Pipeline.xlsx.md', 'Battlecards - card.txt', 'notes.md'])
        self.assertEqual(found['uploads']['notes.md'], (self.folder / 'notes.md').read_bytes())
        # The workbook is read with xlsx_sheets: every sheet under its name.
        self.assertEqual(found['uploads']['Battlecards - Pipeline.xlsx.md'].decode(), xlsx_fixture.SAMPLE_TEXT)
        self.assertEqual({row['name']: row['from'] for row in found['documents']},
                         {'Battlecards - Pipeline.xlsx.md': 'Battlecards/Pipeline.xlsx',
                          'Battlecards - card.txt': 'Battlecards/card.txt', 'notes.md': 'notes.md'})
        self.assertEqual([(row['name'], row['code']) for row in found['skipped']], [('picture.png', 'unsupported')])
        self.assertEqual(found['said'], 'Added 3 documents from “Compete”; 1 was not added. '
                         'Not added: 1 not a type that can be read. 1 hidden file or folder was not looked at.')
        self.assertIsNone(found['next'])
        self.assertEqual(found['report']['added'], 3)

    def test_room_space_and_names_already_taken_are_kept_to(self):
        found = source_intake.take(str(self.folder), accepts=ACCEPTS, room=1, spare=10_000_000, taken=('NOTES.md',))
        self.assertEqual(len(found['uploads']), 1)
        self.assertTrue(all(name.casefold() != 'notes.md' for name in found['uploads']), found['uploads'])
        self.assertIn('over-limit', {row['code'] for row in found['skipped']})
        self.assertEqual(found['next'], 'Give a smaller folder for the rest.')
        tight = source_intake.take(str(self.folder), accepts=ACCEPTS, room=10, spare=30)
        self.assertEqual(list(tight['uploads']), ['Battlecards - card.txt'])
        self.assertIn('the space left', ' '.join(row['reason'] for row in tight['skipped']))

    def test_what_was_given_is_refused_with_a_sentence(self):
        for given in ('relative/folder', str(self.base / 'missing'), 'https://example.invalid/folders/x', ''):
            with self.subTest(given=given), self.assertRaises(ValueError):
                source_intake.take(given, accepts=ACCEPTS, room=10, spare=10_000_000)


class FileTests(unittest.TestCase):
    def test_a_workbook_is_read_as_text_and_a_taken_type_passes_as_it_is(self):
        book = xlsx_fixture.workbook(xlsx_fixture.SAMPLE)
        found = source_intake.take({'name': 'Pipeline.xlsx', 'data': book}, accepts=ACCEPTS, room=5, spare=1_000_000)
        self.assertEqual(found['uploads'], {'Pipeline.xlsx.md': xlsx_fixture.SAMPLE_TEXT.encode()})
        self.assertEqual(found['said'], 'Added “Pipeline.xlsx”. It was read as text.')
        plain = source_intake.take({'name': 'notes.md', 'data': b'# Notes\n'}, accepts=ACCEPTS, room=5, spare=100)
        self.assertEqual(plain['uploads'], {'notes.md': b'# Notes\n'})
        # A studio that keeps workbooks as files is given the workbook itself.
        kept = source_intake.take({'name': 'Pipeline.xlsx', 'data': book}, accepts={'.xlsx'}, room=5, spare=1_000_000)
        self.assertEqual(kept['uploads'], {'Pipeline.xlsx': book})

    def test_what_cannot_be_taken_is_said_and_a_damaged_workbook_is_refused(self):
        left = source_intake.take({'name': 'photo.png', 'data': b'png'}, accepts=ACCEPTS, room=5, spare=100)
        self.assertEqual((left['uploads'], left['skipped'][0]['code']), ({}, 'unsupported'))
        self.assertTrue(left['said'].startswith('“photo.png” was not added. Not a type that can be read.'))
        full = source_intake.take({'name': 'notes.md', 'data': b'# Notes\n'}, accepts=ACCEPTS, room=0, spare=100)
        self.assertEqual(full['skipped'][0]['code'], 'over-limit')
        with self.assertRaises(ValueError):
            source_intake.take({'name': 'broken.xlsx', 'data': b'PK not a workbook'}, accepts=ACCEPTS, room=5, spare=100)
        with self.assertRaises(ValueError):
            source_intake.take({'name': 'empty.md', 'data': b''}, accepts=ACCEPTS, room=5, spare=100)

    def test_names_are_plain_and_never_repeat(self):
        used = {'notes.md'}
        self.assertEqual(source_intake.flat('a/b/notes.md', set()), 'a - b - notes.md')
        self.assertEqual(source_intake.flat('notes.md', used), 'notes (2).md')
        self.assertEqual(source_intake.flat('x:\u202ey/.secret.md', set()), 'x-y - secret.md')
        self.assertLessEqual(len(source_intake.flat('/'.join(['folder' * 5] * 10) + '/end.md', set(), 40)), 40)


if __name__ == '__main__':
    unittest.main()
