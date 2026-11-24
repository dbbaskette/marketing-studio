"""Verified Harness Research in the Document Library: kept, taken by a picker, read back and
refused.

Every test uses a disposable HOME, studios config and library folder, and a synthetic
published bundle (tests/synthesis_fixture.py). Nothing here starts research, an assistant,
a provider or the network.
"""
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import marketing_studio  # noqa: F401  puts the core on the import path
from studio_core import document_library as library
from studio_core.document_library import research, store

from synthesis_fixture import published_bundle

REPORT = '# Restart research\n\nTwo instances keep capacity.\n'
ROOT = Path(__file__).resolve().parents[1]
# Pins one snapshot as Presentation Studio pins it (the shared runner's documents.add_snapshots),
# in its own process, on its own import path and disposable data folder.
PIN = '''
import json, sys
from pathlib import Path
import helpers
sys.path.insert(0, str(helpers.REPO))
from runner import documents
from runner.decks import RUN
deck = Path(sys.argv[2])
(deck / RUN).parent.mkdir(parents=True, exist_ok=True)
(deck / RUN).write_text('{}')    # a deck's folder holds its run record
snapshot = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps(documents.add_snapshots(deck, [snapshot])))
'''


def manifested(folder):
    """Write output.json again with every file's current hash."""
    manifest = json.loads((folder / 'output.json').read_text())
    names = {entry['file'] for entry in manifest['artifacts']} | {'sources/revisions/s1.txt'}
    manifest['artifacts'] = [dict(file=name, sha256=hashlib.sha256((folder / name).read_bytes()).hexdigest())
                             for name in sorted(names)]
    (folder / 'output.json').write_text(json.dumps(manifest))


def bundle(folder, report=REPORT, capture=b'Synthetic capture.\n'):
    """A complete, accepted synthetic bundle with one source capture in its manifest."""
    published_bundle(folder)
    (folder / 'report.md').write_text(report)
    (folder / 'sources/revisions').mkdir(parents=True, exist_ok=True)
    (folder / 'sources/revisions/s1.txt').write_bytes(capture)
    manifested(folder)
    return folder


def zipped(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as out:
        for name, data in files.items():
            out.writestr(name, data)
    return buffer.getvalue()


class ResearchCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        patcher = mock.patch.dict(os.environ, {'HOME': str(self.base / 'home'),
                                               'STUDIOS_CONFIG': str(self.base / 'studios-config.json'),
                                               'STUDIOS_LIBRARY': str(self.base / 'library')})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.library = library.opened(create=True)
        self.project = self.base / 'restart'
        self.folder = bundle(self.project / 'research')

    def keep(self, **extra):
        return research.keep_research(self.library, studio='training', project='restart-1a2b3c',
                                      case=self.folder, **extra)


class KeepTests(ResearchCase):
    def test_a_verified_bundle_is_kept_once_as_a_readable_research_item(self):
        kept = self.keep(author='Pat')
        self.assertEqual(kept['state'], 'kept', kept)
        self.assertEqual(kept['key'], 'training:restart-1a2b3c:research')
        self.assertTrue(kept['changed'])
        row = self.library.describe(kept['document'])
        self.assertEqual((row['kind'], row['kind_label'], row['title'], row['studio']),
                         ('research', 'Research', 'Restart research', 'training'))
        self.assertTrue(row['readable'])
        self.assertEqual(row['formats'], ['markdown', 'original'])
        self.assertEqual(row['original_name'], 'restart-research-research.zip')
        held = self.library.research_archive(kept['document'], kept['revision'])
        with zipfile.ZipFile(io.BytesIO(held['archive'])) as packed:
            self.assertEqual(sorted(packed.namelist()), sorted(['output.json', 'report.md', 'brief.md', 'evidence.md',
                                                                 'facts.json', 'sources/revisions/s1.txt']))
            # The exact output.json bytes that were checked are the ones archived.
            self.assertEqual(packed.read('output.json'), (self.folder / 'output.json').read_bytes())
        self.assertEqual(self.library.catalog(kind='research')['total'], 1)
        again = self.keep(author='Pat')
        self.assertEqual((again['document'], again['revision'], again['changed']),
                         (kept['document'], kept['revision'], False))
        bundle(self.folder, report='# Restart research\n\nThree instances now.\n')
        newer = self.keep()
        self.assertEqual((newer['document'], newer['revision'], newer['changed']), (kept['document'], 2, True))

    def test_a_picker_takes_research_as_its_report_alone(self):
        kept = self.keep()
        found = self.library.snapshot(kept['document'], kept['revision'])
        self.assertIsNone(found['original'])
        self.assertIsNone(found['original_sha256'])
        self.assertEqual((found['name'], found['text']), ('restart-research.md', REPORT))
        # Pinned as Presentation Studio and the shared runner pin a document: its report.
        item = self.base / 'item'
        item.mkdir()
        (self.base / 'snapshot.json').write_text(json.dumps(found))
        done = subprocess.run([sys.executable, '-c', PIN, str(self.base / 'snapshot.json'), str(item)],
                              cwd=ROOT / 'studios/presentation/tests', capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        entry = json.loads(done.stdout)[0]
        self.assertEqual(entry['name'], 'restart-research.md')
        self.assertEqual(entry['library']['kind'], 'research')
        kept_files = [path for path in item.rglob('*') if path.is_file() and path.suffix in ('.md', '.txt')]
        self.assertTrue(any(path.read_text() == REPORT for path in kept_files), kept_files)
        self.assertFalse(any(path.read_bytes().startswith(b'PK') for path in item.rglob('*') if path.is_file()),
                         'no archive is pinned as a source')

    def test_the_same_research_archived_again_differently_adds_no_revision(self):
        kept = self.keep()
        # Another zlib, another archive: the same title, report and output.json are the same research.
        with mock.patch.object(research.zipfile, 'ZIP_DEFLATED', zipfile.ZIP_STORED):
            again = self.keep()
        self.assertEqual((again['revision'], again['changed']), (kept['revision'], False))

    def test_a_file_changed_after_verification_is_not_archived(self):
        real = research.contract.read_bundle

        def then_changed(name):
            def reading(folder, *args, **kwargs):
                answer = real(folder, *args, **kwargs)
                path = Path(folder) / name
                if name == 'output.json':     # still a manifest, and a different one
                    path.write_text(json.dumps({**json.loads(path.read_text()), 'note': 'changed'}))
                else:
                    path.write_bytes(path.read_bytes() + b'changed\n')
                return answer
            return reading
        for name in ('sources/revisions/s1.txt', 'output.json'):
            with self.subTest(name=name):
                bundle(self.folder)
                with mock.patch.object(research.contract, 'read_bundle', then_changed(name)):
                    found = self.keep()
                self.assertEqual(found['state'], 'refused', found)
                self.assertIn('changed', found['problem'])
        self.assertEqual(self.library.catalog()['total'], 0)

    def test_research_and_finished_work_of_one_project_are_two_documents(self):
        work = self.library.retain(key='training:restart-1a2b3c', studio='training', kind='training',
                                   title='Restart', text='# Guide\n')
        kept = self.keep(title='Restart: research')
        self.assertNotEqual(work['document'], kept['document'])
        self.assertEqual(set(self.library.keyed(['training:restart-1a2b3c', kept['key']])),
                         {'training:restart-1a2b3c', 'training:restart-1a2b3c:research'})
        with self.assertRaises(library.LibraryError):
            self.library.retain(key='training:restart-1a2b3c', studio='training', kind='research',
                                title='Restart', text='# Guide\n')
        with self.assertRaises(library.LibraryError):
            self.library.retain(key='training:restart-1a2b3c:research', studio='training', kind='training',
                                title='Restart', text='# Guide\n')
        # Add existing work cannot make research either: research always carries its bundle.
        with self.assertRaises(library.LibraryError):
            self.library.adopt(key='training:restart-1a2b3c', studio='training', kind='research',
                               origin='imported', title='Restart', text='# Guide\n')

    def test_a_bundle_that_does_not_pass_verification_is_refused_and_nothing_is_kept(self):
        draft = self.base / 'draft/research'
        published_bundle(draft, review=dict(accepted=False, digest='synthetic-digest'))
        changed = bundle(self.base / 'changed/research')
        (changed / 'sources/revisions/s1.txt').write_text('Edited after review.\n')
        for case in (draft, changed):
            with self.subTest(case=case.relative_to(self.base).as_posix()):
                found = research.keep_research(self.library, studio='training', project='restart-1a2b3c', case=case)
                self.assertEqual(found['state'], 'refused', found)
                self.assertIn('has not passed verification', found['problem'])
        self.assertEqual(self.library.catalog()['total'], 0)

    def test_files_that_cannot_be_read_are_a_failure_not_a_refusal(self):
        for case in (self.base / 'missing', self.base / 'nothing-here/research'):
            with self.subTest(case=case.name):
                found = research.keep_research(self.library, studio='training', project='restart-1a2b3c', case=case)
                self.assertEqual(found['state'], 'failed', found)
                self.assertIn('could not be read', found['problem'])
                self.assertNotIn('verification', found['problem'])
        with mock.patch.object(research.contract, 'read_bundle', side_effect=PermissionError(13, 'Permission denied')):
            found = self.keep()
        self.assertEqual(found['state'], 'failed')
        self.assertEqual(self.library.catalog()['total'], 0)

    def test_it_never_raises_into_its_caller(self):
        for studio, project in (('marketing', 'restart'), ('training', '../escape'), ('training', None)):
            found = research.keep_research(self.library, studio=studio, project=project, case=self.folder)
            self.assertEqual(found['state'], 'failed')
        with mock.patch.object(store.Library, 'retain_research', side_effect=RuntimeError('boom')):
            found = self.keep()
        self.assertEqual((found['state'], found['problem']), ('failed', research.NOT_KEPT))
        with mock.patch.object(research.contract, 'read_bundle', side_effect=RuntimeError('boom')):
            self.assertEqual(self.keep()['state'], 'refused')
        found = research.keep_research(None, studio='training', project={'id': 'restart-1a2b3c', 'title': 'Restart'},
                                       case=self.folder)
        self.assertEqual(found['state'], 'kept', found)
        self.assertEqual(self.library.describe(found['document'])['project']['title'], 'Restart')

    def test_a_bundle_may_be_up_to_sixteen_megabytes_zipped_and_no_other_limit_moves(self):
        self.assertEqual((store.LIMITS['research'], store.LIMITS['bytes']), (16_000_000, 8_000_000))
        large = b'PK' + os.urandom(12_000_000)
        kept = self.library.retain_research(key='training:large:research', studio='training', title='Large',
                                            text='# Large\n', bundle=large)
        held = self.library.research_archive(kept['document'], kept['revision'])
        self.assertEqual(held['archive'], large)
        self.assertEqual(self.library.download(kept['document'], kept['revision'], 'original')[2], large)
        again = self.library.retain_research(key='training:large:research', studio='training', title='Large',
                                             text='# Large\n', bundle=large)
        self.assertFalse(again['changed'], 'a whole large bundle is the same document')
        with self.assertRaisesRegex(library.LibraryError, '16 MB'):
            self.library.retain_research(key='training:huge:research', studio='training', title='Huge',
                                         text='# Huge\n', bundle=b'PK' + bytes(16_000_000))
        with self.assertRaisesRegex(library.LibraryError, '8 MB'):
            self.library.add_upload('big.txt', b'x' * 8_000_001)

    def test_existing_records_read_unchanged_with_no_migration(self):
        work = self.library.retain(key='blog:launch-1', studio='blog', kind='blog', title='Launch', text='# Launch\n')
        record = self.library.root / 'documents' / work['document'] / 'revisions/1/revision.json'
        before = record.read_bytes()
        self.keep()
        self.assertEqual(record.read_bytes(), before)
        self.assertEqual(self.library.describe(work['document'])['kind'], 'blog')
        self.assertEqual(self.library.catalog(kind='blog')['total'], 1)


class ReadBackTests(ResearchCase):
    def setUp(self):
        super().setUp()
        self.kept = self.keep()

    def test_the_bundle_comes_back_as_files_that_pass_verification(self):
        (self.base / 'imported').mkdir()
        target = self.base / 'imported/research'
        found = research.research_bundle(self.library, self.kept['document'], self.kept['revision'], target)
        self.assertEqual(found['folder'], str(target))
        self.assertEqual(found['digest'], 'synthetic-digest')
        self.assertIn('sources/revisions/s1.txt', found['files'])
        for name in found['files']:
            self.assertEqual((target / name).read_bytes(), (self.folder / name).read_bytes(), name)
        empty = self.base / 'empty'
        empty.mkdir()
        research.research_bundle(None, self.kept['document'], self.kept['revision'], empty)
        with self.assertRaisesRegex(library.LibraryError, 'new or empty folder'):
            research.research_bundle(self.library, self.kept['document'], self.kept['revision'], target)
        with self.assertRaisesRegex(library.LibraryError, 'absolute folder'):
            research.research_bundle(self.library, self.kept['document'], self.kept['revision'], 'relative')

    def test_only_the_named_folder_is_made_and_missing_parents_are_refused(self):
        deep = self.base / 'not/there/research'
        with self.assertRaisesRegex(library.LibraryError, 'parent folder'):
            research.research_bundle(self.library, self.kept['document'], 1, deep)
        self.assertFalse((self.base / 'not').exists(), 'no parent folder is left behind')

    def test_ids_and_revisions_are_checked_before_the_library_is_read(self):
        with mock.patch.object(store.Library, 'research_archive', side_effect=AssertionError('read')):
            for ident, revision in (('../x', 1), ('UPPER', 1), (None, 1), (self.kept['document'], '1'),
                                    (self.kept['document'], True), (self.kept['document'], 0),
                                    (self.kept['document'], 1001)):
                with self.subTest(ident=ident, revision=revision), \
                        self.assertRaisesRegex(library.LibraryError, 'by its ID and revision'):
                    research.research_bundle(self.library, ident, revision, self.base / 'x')

    def test_other_documents_and_changed_bundles_are_refused_and_nothing_is_left(self):
        work = self.library.retain(key='blog:launch-1', studio='blog', kind='blog', title='Launch', text='# Launch\n')
        with self.assertRaisesRegex(library.LibraryError, 'not research'):
            research.research_bundle(self.library, work['document'], 1, self.base / 'one')
        self.assertFalse((self.base / 'one').exists())
        place = self.library.root / 'documents' / self.kept['document'] / 'revisions/1'
        original = (place / store.BUNDLE_FILE).read_bytes()
        (place / store.BUNDLE_FILE).write_bytes(original + b'x')
        with self.assertRaises(library.LibraryError):
            research.research_bundle(self.library, self.kept['document'], 1, self.base / 'two')
        self.assertFalse((self.base / 'two').exists())
        (place / store.BUNDLE_FILE).write_bytes(original)

    def test_an_archive_whose_names_escape_are_unlisted_or_whose_files_changed_is_refused(self):
        original = self.library.research_archive(self.kept['document'], 1)['archive']

        def tampered(name, data, kind=stat.S_IFREG):
            buffer = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(buffer, 'w') as out:
                for info in source.infolist():
                    out.writestr(info, source.read(info))
                extra = zipfile.ZipInfo(name)
                extra.external_attr = (kind | 0o600) << 16
                out.writestr(extra, data)
            return buffer.getvalue()

        def replaced(edit):
            buffer = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(buffer, 'w') as out:
                for info in source.infolist():
                    out.writestr(info, edit(info.filename, source.read(info)))
            return buffer.getvalue()

        cases = {'escape': tampered('../outside.txt', b'x'), 'absolute': tampered('/tmp/x', b'x'),
                 'link': tampered('sources/link', b'/etc/hosts', stat.S_IFLNK),
                 'unlisted': tampered('notes/extra.txt', b'not in the manifest'),
                 'capture-edited': replaced(lambda name, data: b'Edited.\n' if name.endswith('s1.txt') else data)}
        for label, archive in cases.items():
            with self.subTest(label):
                kept = self.library.retain_research(key=f'training:{label}:research', studio='training',
                                                    title=label, text=REPORT, bundle=archive)
                (self.base / 'into').mkdir(exist_ok=True)
                target = self.base / 'into' / label
                with self.assertRaises(library.LibraryError):
                    research.research_bundle(self.library, kept['document'], kept['revision'], target)
                self.assertFalse(target.exists(), 'what was written is cleared')
                self.assertFalse((self.base / 'into/outside.txt').exists())

    def test_a_hidden_item_is_not_imported(self):
        self.library.hide(self.kept['document'])
        with self.assertRaisesRegex(library.LibraryError, 'removed from the library'):
            research.research_bundle(self.library, self.kept['document'], 1, self.base / 'hidden')


if __name__ == '__main__':
    unittest.main()
