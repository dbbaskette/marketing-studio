"""A part's kept versions: one JSON line each, newest last on disk, newest first when read."""

import os
import tempfile
import unittest

from drafting_fixtures import FolderStore, draft, make
from studio_core.drafting import versions
from studio_core.drafting.versions import SOURCES, Versions

NOT_PLAIN = 'A desk versions file is not a plain file. Nothing was changed.'


class VersionsCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = FolderStore(folder.name)
        make(self.store, 'one', draft())
        self.kept = Versions(self.store)


class VersionTests(VersionsCase):
    def test_twenty_versions_are_kept_per_part_newest_first(self):
        for number in range(25):
            self.kept.keep('one', 'opening', 'Text ' + str(number), 'rewrite')
        found = self.kept.versions('one', 'opening')
        self.assertEqual(len(found), 20)
        self.assertEqual(found[0]['text'], 'Text 24')
        self.assertEqual(found[-1]['text'], 'Text 5')

    def test_saves_from_one_editing_session_keep_only_the_first_text(self):
        session = 'a' * 16
        self.kept.keep('one', 'opening', 'First', 'save', session)
        self.kept.keep('one', 'opening', 'Second', 'save', session)
        self.assertEqual([v['text'] for v in self.kept.versions('one', 'opening')], ['First'])
        self.kept.keep('one', 'opening', 'Third', 'rewrite')
        self.assertEqual(len(self.kept.versions('one', 'opening')), 2)

    def test_a_torn_line_hides_no_other_version(self):
        self.kept.keep('one', 'opening', 'One', 'rewrite')
        self.kept.keep('one', 'opening', 'Two', 'rewrite')
        with open(self.kept.path('one', 'opening'), 'a', encoding='utf-8') as file:
            file.write('{not json\n')
        self.assertEqual([v['text'] for v in self.kept.versions('one', 'opening')], ['Two', 'One'])

    def test_a_linked_versions_folder_is_refused(self):
        elsewhere = self.store.root / 'elsewhere'
        elsewhere.mkdir()
        os.symlink(elsewhere, self.store.path('one', 'versions'))
        with self.assertRaisesRegex(ValueError, NOT_PLAIN):
            self.kept.keep('one', 'opening', 'One', 'rewrite')

    def test_only_listed_sources_and_known_parts(self):
        with self.assertRaisesRegex(ValueError, 'Choose a listed kind of change.'):
            self.kept.keep('one', 'opening', 'One', 'chat')
        Versions(self.store, sources=SOURCES + ('chat',)).keep('one', 'opening', 'One', 'chat')
        with self.assertRaisesRegex(ValueError, 'Choose a part of this draft.'):
            self.kept.path('one', '../x')

    def test_counts_name_only_parts_with_versions(self):
        self.kept.keep('one', 'aaaaaaaa', 'One', 'rewrite')
        self.kept.keep('one', 'aaaaaaaa', 'Two', 'rewrite')
        self.kept.keep('one', 'title', 'Old title', 'save')
        (self.store.path('one', 'versions') / 'notes.jsonl').write_text('{"text": "x"}\n')
        (self.store.path('one', 'versions') / 'opening.jsonl').write_text('')
        self.assertEqual(self.kept.counts('one'), {'aaaaaaaa': 2, 'title': 1})
        self.assertEqual(Versions(self.store).counts('two'), {})

    def test_an_entry_names_its_time_source_text_and_words(self):
        self.kept.keep('one', 'opening', 'Three short words', 'rewrite', extra={'divided': ['x']})
        entry = versions.entries(self.kept.path('one', 'opening'))[0]
        self.assertEqual(entry['source'], 'rewrite')
        self.assertEqual(entry['words'], 3)
        self.assertEqual(entry['divided'], ['x'])
        self.assertIn('at', entry)


if __name__ == '__main__':
    unittest.main()
