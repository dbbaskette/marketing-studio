"""Verified Harness Research in the Document Library: kept, read back and refused.

Every test uses a disposable HOME, studios config and library folder, and a synthetic
published bundle (tests/synthesis_fixture.py). Nothing here starts research, an assistant,
a provider or the network.
"""
import hashlib
import io
import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import marketing_studio  # noqa: F401  puts the core on the import path
from studio_core import document_library as library
from studio_core.document_library import research, store

from synthesis_fixture import published_bundle


def bundle(folder, report='# Restart research\n\nTwo instances keep capacity.\n', capture=b'Synthetic capture.\n'):
    """A complete, accepted synthetic bundle with one source capture in its manifest."""
    published_bundle(folder)
    (folder / 'report.md').write_text(report)
    (folder / 'sources/revisions').mkdir(parents=True, exist_ok=True)
    (folder / 'sources/revisions/s1.txt').write_bytes(capture)
    manifest = json.loads((folder / 'output.json').read_text())
    manifest['artifacts'] = [dict(file=name, sha256=hashlib.sha256((folder / name).read_bytes()).hexdigest())
                             for name in sorted({*(e['file'] for e in manifest['artifacts']), 'sources/revisions/s1.txt'})]
    (folder / 'output.json').write_text(json.dumps(manifest))
    return folder


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
        # Every existing picker takes it through snapshot: the report as text, the bundle as its original.
        found = self.library.snapshot(kept['document'], kept['revision'])
        self.assertEqual(found['text'], (self.folder / 'report.md').read_text())
        with zipfile.ZipFile(io.BytesIO(found['original'])) as packed:
            self.assertEqual(sorted(packed.namelist()), sorted(['output.json', 'report.md', 'brief.md', 'evidence.md',
                                                                 'facts.json', 'sources/revisions/s1.txt']))
        self.assertEqual(self.library.catalog(kind='research')['total'], 1)
        # The same bundle again is the same original: no new revision.
        again = self.keep(author='Pat')
        self.assertEqual((again['document'], again['revision'], again['changed']),
                         (kept['document'], kept['revision'], False))
        # A changed report is a new revision of the same document.
        bundle(self.folder, report='# Restart research\n\nThree instances now.\n')
        newer = self.keep()
        self.assertEqual((newer['document'], newer['revision'], newer['changed']), (kept['document'], 2, True))

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

    def test_a_bundle_that_does_not_pass_verification_is_refused_and_nothing_is_kept(self):
        facts = json.loads((self.folder / 'facts.json').read_text())
        draft = self.base / 'draft/research'
        published_bundle(draft, review=dict(accepted=False, digest='synthetic-digest'))
        changed = bundle(self.base / 'changed/research')
        (changed / 'sources/revisions/s1.txt').write_text('Edited after review.\n')
        for case in (draft, changed, self.base / 'missing', self.base / 'nothing-here/research'):
            with self.subTest(case=case.relative_to(self.base).as_posix()):
                found = research.keep_research(self.library, studio='training', project='restart-1a2b3c', case=case)
                self.assertEqual(found['state'], 'refused', found)
                self.assertIn('has not passed verification', found['problem'])
        self.assertEqual(self.library.catalog()['total'], 0)
        self.assertEqual(facts['status'], 'complete')

    def test_it_never_raises_into_its_caller(self):
        for studio, project in (('marketing', 'restart'), ('training', '../escape'), ('training', None)):
            found = research.keep_research(self.library, studio=studio, project=project, case=self.folder)
            self.assertEqual(found['state'], 'failed')
        with mock.patch.object(store.Library, 'retain_research', side_effect=RuntimeError('boom')):
            found = self.keep()
        self.assertEqual((found['state'], found['problem']), ('failed', research.NOT_KEPT))
        with mock.patch.object(research.contract, 'read_bundle', side_effect=RuntimeError('boom')):
            self.assertEqual(self.keep()['state'], 'refused')
        # None opens (and on first use makes) the shared library itself.
        found = research.keep_research(None, studio='training', project={'id': 'restart-1a2b3c', 'title': 'Restart'},
                                       case=self.folder)
        self.assertEqual(found['state'], 'kept', found)
        self.assertEqual(self.library.describe(found['document'])['project']['title'], 'Restart')

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
        target = self.base / 'imported/research'
        found = research.research_bundle(self.library, self.kept['document'], self.kept['revision'], target)
        self.assertEqual(found['folder'], str(target))
        self.assertEqual(found['digest'], 'synthetic-digest')
        self.assertIn('sources/revisions/s1.txt', found['files'])
        for name in found['files']:
            self.assertEqual((target / name).read_bytes(), (self.folder / name).read_bytes(), name)
        # An empty folder that is already there is used too; one that holds anything is refused.
        empty = self.base / 'empty'
        empty.mkdir()
        research.research_bundle(None, self.kept['document'], self.kept['revision'], empty)
        with self.assertRaisesRegex(library.LibraryError, 'new or empty folder'):
            research.research_bundle(self.library, self.kept['document'], self.kept['revision'], target)
        with self.assertRaisesRegex(library.LibraryError, 'absolute folder'):
            research.research_bundle(self.library, self.kept['document'], self.kept['revision'], 'relative')

    def test_other_documents_and_changed_bundles_are_refused_and_nothing_is_left(self):
        work = self.library.retain(key='blog:launch-1', studio='blog', kind='blog', title='Launch', text='# Launch\n')
        with self.assertRaisesRegex(library.LibraryError, 'not research'):
            research.research_bundle(self.library, work['document'], 1, self.base / 'one')
        self.assertFalse((self.base / 'one').exists())
        # The kept archive changed on disk: its hash refuses it before anything is written.
        place = self.library.root / 'documents' / self.kept['document'] / 'revisions/1'
        original = (place / store.BUNDLE_FILE).read_bytes()
        (place / store.BUNDLE_FILE).write_bytes(original + b'x')
        with self.assertRaises(library.LibraryError):
            research.research_bundle(self.library, self.kept['document'], 1, self.base / 'two')
        self.assertFalse((self.base / 'two').exists())
        (place / store.BUNDLE_FILE).write_bytes(original)

    def test_an_archive_whose_names_escape_or_whose_files_changed_is_refused(self):
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

        original = self.library.snapshot(self.kept['document'], 1)['original']
        cases = {'escape': tampered('../outside.txt', b'x'), 'absolute': tampered('/tmp/x', b'x'),
                 'link': tampered('sources/link', b'/etc/hosts', stat.S_IFLNK),
                 'capture-edited': replaced(lambda name, data: b'Edited.\n' if name.endswith('s1.txt') else data)}
        for label, archive in cases.items():
            with self.subTest(label):
                kept = self.library.retain_research(key=f'training:{label}:research', studio='training',
                                                    title=label, text=(self.folder / 'report.md').read_text(),
                                                    bundle=archive)
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
