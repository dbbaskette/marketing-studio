"""Faults while publishing a prepared Training Studio slide edit."""
import sys
from unittest import mock

from helpers import REPO, TrainingCase

sys.path.insert(0, str(REPO))
from runner import deck_edit
from workspace import WorkspaceError


class PublicationTests(TrainingCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(deck_edit.home, 'data_root', return_value=self.root.parent / 'data')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.write('a.txt', 'old a')
        self.write('b.txt', 'old b')

    def test_failed_write_restores_only_what_this_edit_wrote(self):
        write = deck_edit.write_atomic
        with deck_edit.PreparedEdit(self.root) as edit:
            (edit.root / 'a.txt').write_text('new a')
            (edit.root / 'b.txt').write_text('new b')
            calls = []

            def fail(file, data):
                calls.append(file)
                if len(calls) == 2:
                    self.write('unrelated.txt', 'someone else')
                    raise OSError('Disk refused the write')
                write(file, data)

            with mock.patch.object(deck_edit, 'write_atomic', side_effect=fail):
                with self.assertRaisesRegex(OSError, 'Disk refused'):
                    edit.publish()
        self.assertEqual((self.root / 'a.txt').read_text(), 'old a')
        self.assertEqual((self.root / 'b.txt').read_text(), 'old b')
        self.assertEqual((self.root / 'unrelated.txt').read_text(), 'someone else')
        deck_edit.check_pending(self.root)

    def test_write_then_failure_is_also_rolled_back(self):
        write = deck_edit.write_atomic
        with deck_edit.PreparedEdit(self.root) as edit:
            (edit.root / 'a.txt').write_text('new a')
            calls = []

            def fail(file, data):
                write(file, data)
                calls.append(file)
                if len(calls) == 1:
                    raise OSError('Failed after replacement')

            with mock.patch.object(deck_edit, 'write_atomic', side_effect=fail):
                with self.assertRaisesRegex(OSError, 'Failed after replacement'):
                    edit.publish()
        self.assertEqual((self.root / 'a.txt').read_text(), 'old a')

    def test_later_change_is_preserved_and_recovery_blocks_another_edit(self):
        write = deck_edit.write_atomic
        with deck_edit.PreparedEdit(self.root) as edit:
            (edit.root / 'a.txt').write_text('new a')
            (edit.root / 'b.txt').write_text('new b')
            calls = []

            def fail(file, data):
                if len(calls) == 1:
                    calls[0].write_text('someone else')
                    raise OSError('Disk refused the write')
                calls.append(file)
                write(file, data)

            with mock.patch.object(deck_edit, 'write_atomic', side_effect=fail):
                with self.assertRaisesRegex(WorkspaceError, 'Later changes were left alone'):
                    edit.publish()
        self.assertEqual(calls[0].read_text(), 'someone else')
        self.assertTrue((edit.folder / 'PUBLISHING.txt').is_file())
        self.assertEqual(edit.root.name, self.root.name)
        self.assertIn('Prepared: prepared/' + self.root.name + '/', (edit.folder / 'PUBLISHING.txt').read_text())
        self.assertEqual((edit.before / calls[0].name).read_text(), 'old ' + calls[0].stem)
        with self.assertRaisesRegex(WorkspaceError, 'interrupted slide save needs recovery'):
            deck_edit.PreparedEdit(self.root)

    def test_historical_recovery_folder_still_blocks_without_mutation(self):
        folder = deck_edit.storage(self.root) / 'edit-historical'
        (folder / 'prepared').mkdir(parents=True)
        (folder / 'prepared/a.txt').write_text('historical prepared bytes')
        journal = folder / 'PUBLISHING.txt'
        journal.write_text('Training Studio slide edit\nBefore: before/\nPrepared: prepared/\n')
        before = {path.relative_to(folder): path.read_bytes() for path in folder.rglob('*') if path.is_file()}
        with self.assertRaisesRegex(WorkspaceError, 'interrupted slide save needs recovery'):
            deck_edit.PreparedEdit(self.root)
        self.assertEqual({path.relative_to(folder): path.read_bytes() for path in folder.rglob('*') if path.is_file()}, before)

    def test_another_training_command_prevents_publication(self):
        from workspace import locked
        with deck_edit.PreparedEdit(self.root) as edit:
            (edit.root / 'a.txt').write_text('new a')
            with locked(self.root):
                with self.assertRaisesRegex(WorkspaceError, 'Another Training Studio command'):
                    edit.publish()
        self.assertEqual((self.root / 'a.txt').read_text(), 'old a')

    def test_journal_cleanup_failure_retains_published_round_and_recovery(self):
        from pathlib import Path
        unlink = Path.unlink
        with self.assertRaises((OSError, WorkspaceError)):
            with deck_edit.PreparedEdit(self.root) as edit:
                (edit.root / 'a.txt').write_text('new a')
                drawn = edit.output_folder(edit.root / 'whole-new')
                drawn.mkdir()
                (drawn / 'deck.pptx').write_bytes(b'new deck')
                edit.seal_output(drawn)
                (edit.root / 'whole-new').mkdir()
                (edit.root / 'whole-new' / 'deck.pptx').write_bytes(b'new deck')

                def fail(file, *args, **kwargs):
                    if file.name == 'PUBLISHING.txt':
                        raise PermissionError('Cannot remove the journal')
                    return unlink(file, *args, **kwargs)

                with mock.patch.object(Path, 'unlink', fail):
                    edit.publish()
        self.assertEqual((self.root / 'a.txt').read_text(), 'new a')
        self.assertEqual((drawn / 'deck.pptx').read_bytes(), b'new deck')
        self.assertTrue((edit.folder / 'PUBLISHING.txt').is_file())
        self.assertTrue(edit.before.is_dir())
        self.assertTrue(edit.root.is_dir())
        with self.assertRaisesRegex(WorkspaceError, 'interrupted slide save needs recovery'):
            deck_edit.check_pending(self.root)

    def test_a_new_design_project_can_be_updated_before_publication(self):
        with deck_edit.PreparedEdit(self.root) as edit:
            folder = edit.output_folder(edit.root / 'new-project')
            folder.mkdir()
            (folder / 'session.json').write_text('approved design')
            edit.seal_output(folder)
            (edit.root / 'new-project').mkdir()
            (edit.root / 'new-project' / 'session.json').write_text('presented deck')
            edit.publish()
        self.assertEqual((folder / 'session.json').read_text(), 'presented deck')

    def test_a_new_design_project_write_failure_restores_the_old_training(self):
        write = deck_edit.write_atomic
        with deck_edit.PreparedEdit(self.root) as edit:
            folder = edit.output_folder(edit.root / 'new-project')
            folder.mkdir()
            (folder / 'session.json').write_text('approved design')
            edit.seal_output(folder)
            (edit.root / 'new-project').mkdir()
            (edit.root / 'new-project' / 'session.json').write_text('presented deck')
            (edit.root / 'a.txt').write_text('new a')

            def fail(path, data):
                write(path, data)
                if path.name == 'session.json':
                    raise OSError('Session write failed after replacement')

            with mock.patch.object(deck_edit, 'write_atomic', side_effect=fail):
                with self.assertRaisesRegex(OSError, 'Session write failed'):
                    edit.publish()
        self.assertEqual((self.root / 'a.txt').read_text(), 'old a')
        self.assertFalse(folder.exists())
        deck_edit.check_pending(self.root)

    def test_old_and_levelled_project_paths_keep_their_original_locations(self):
        from runner import pipeline
        self.assertEqual(pipeline.design_project(self.root, None), self.root / 'deck')
        self.assertEqual(pipeline.design_project(self.root, '101'), self.root / '101' / 'deck')
        project = 'deck/design-edits/' + 'a' * 24
        selected = pipeline.design_project(self.root, '101', {'project': project})
        self.assertEqual(selected, self.root / '101' / project)
        with self.assertRaisesRegex(WorkspaceError, 'cannot be opened safely'):
            pipeline.design_project(self.root, None, {'project': '../another-training'})

    def test_shared_approval_takes_precedence_over_an_older_local_build(self):
        from runner import drafts, pipeline
        old, current = ('deck/design-edits/' + letter * 24 for letter in ('a', 'b'))
        pipeline.write_built(self.root, '101', {'start': {'design': {'project': old}}})
        deck_edit.home.write_json(self.root / drafts.RECORD,
            {'deck': {'101': {'approved': {'design': {'project': current}}}}})
        self.assertEqual(pipeline.design_project(self.root, '101'), self.root / '101' / current)
        # Rendering an explicitly selected revision still uses that revision's project.
        self.assertEqual(pipeline.design_project(self.root, '101', {'project': old}),
                         self.root / '101' / old)
