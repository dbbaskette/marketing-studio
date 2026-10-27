"""The desk record: the per-part check, saves and removed parts, over a disposable store."""

import tempfile
import unittest

from drafting_fixtures import FolderStore, draft, make
from studio_core.drafting import record
from studio_core.drafting.parts import Codec

OLD = 'This draft changed since you opened it. Reload to see the latest.'


class RecordCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = FolderStore(folder.name)
        self.desk = record.Desk(self.store)
        make(self.store, 'one', draft())


class RecordTests(RecordCase):
    def test_a_form_older_than_one_part_may_still_change_another(self):
        self.assertEqual(self.desk.save('one', 1, 'aaaaaaaa', 'New first.')['revision'], 2)
        self.assertEqual(self.desk.save('one', 1, 'bbbbbbbb', 'New second.')['revision'], 3)
        with self.assertRaisesRegex(ValueError, '^' + OLD + '$'):
            self.desk.save('one', 1, 'aaaaaaaa', 'Older form.')

    def test_with_no_parts_named_the_whole_item_must_be_as_seen(self):
        value = {**draft(), 'revision': 2}
        with self.assertRaisesRegex(ValueError, OLD):
            self.desk.checked(value, 1)
        self.desk.checked(value, 2)
        for seen in (True, 3, '2'):
            with self.assertRaisesRegex(ValueError, OLD):
                self.desk.checked(value, seen)

    def test_the_same_text_again_is_not_refused(self):
        self.desk.save('one', 1, 'aaaaaaaa', 'New first.')
        self.store.written.clear()
        self.assertEqual(self.desk.save('one', 1, 'aaaaaaaa', 'New first.  ')['revision'], 2)
        self.assertEqual(self.store.written, [])

    def test_a_part_keeps_its_text_as_a_version_before_it_changes(self):
        self.desk.save('one', 1, 'aaaaaaaa', 'New first.')
        kept = self.desk.versions.versions('one', 'aaaaaaaa')[0]
        self.assertEqual((kept['text'], kept['source'], kept['words']), ('First text.', 'save', 2))
        self.assertEqual(self.store.written, [('one', ['aaaaaaaa'])])
        saved = self.store.read('one')
        self.assertEqual(saved['changed'], {'aaaaaaaa': 2})

    def test_a_one_line_part_and_a_new_heading_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'Keep the title to one line, up to 500 characters.'):
            self.desk.checked_text('title', 'a\nb')
        with self.assertRaisesRegex(ValueError, 'A ## heading would start a new section.'):
            self.desk.checked_text('aaaaaaaa', '## New')
        with self.assertRaisesRegex(ValueError, 'Keep one part under 200,000 characters.'):
            self.desk.checked_text('opening', 'x' * 200_001)

    def test_a_restore_brings_back_a_version_and_keeps_the_text_it_replaces(self):
        self.desk.save('one', 1, 'opening', 'Changed opening.')
        self.desk.restore('one', 2, 'opening', 0)
        self.assertEqual(self.store.read('one')['opening'], 'An opening paragraph.')
        kept = self.desk.versions.versions('one', 'opening')
        self.assertEqual([(v['source'], v['text']) for v in kept][0], ('restore', 'Changed opening.'))
        with self.assertRaisesRegex(ValueError, 'Choose a saved version.'):
            self.desk.restore('one', 3, 'opening', 9)

    def test_a_removed_section_comes_back_where_it_was_with_its_id(self):
        second = self.store.read('one')['sections'][1]
        self.desk.keep_removed('one', [{**second, 'index': 1, 'at': 'now'}])
        value = self.store.read('one')
        value['sections'] = value['sections'][:1]
        make(self.store, 'one', value)
        self.desk.unremove('one', 1, 0)
        back = self.store.read('one')['sections']
        self.assertEqual([s['id'] for s in back], ['aaaaaaaa', 'bbbbbbbb'])
        self.assertEqual(back[1]['text'], 'Second text.')
        self.assertEqual(self.desk.removed('one'), [])
        with self.assertRaisesRegex(ValueError, 'Choose a removed section.'):
            self.desk.unremove('one', 2, 0)

    def test_writes_need_the_lock(self):
        self.store.lock = False
        with self.assertRaisesRegex(RuntimeError, 'Desk writes run under the studio lock.'):
            self.desk.save('one', 1, 'aaaaaaaa', 'New first.')

    def test_an_item_that_is_not_on_the_desk_is_said_with_the_studio_s_word(self):
        with self.assertRaisesRegex(ValueError, 'This item is not on the desk.'):
            self.desk.read('two')

    def test_a_deck_worded_desk_says_deck(self):
        deck = record.Desk(self.store, Codec(thing='deck'))
        with self.assertRaisesRegex(ValueError, 'This deck changed since you opened it.'):
            deck.checked({**draft(), 'revision': 2}, 1)

    def test_a_codec_s_hooks_take_and_fit_what_a_save_carries(self):
        def taken(value, part, text, previous):
            return text.replace('[pic]', ''), {**value, 'pics': ['pic']}

        def fitted(value, before):
            return {**value, 'fitted': before['revision']}

        desk = record.Desk(self.store, Codec(taken=taken, fitted=fitted))
        saved = desk.save('one', 1, 'opening', 'With a picture.[pic]')
        self.assertEqual(
            (saved['opening'], saved['pics'], saved['fitted']), ('With a picture.', ['pic'], 1)
        )

    def test_advance_marks_each_part_at_the_new_revision(self):
        value = record.advance({'revision': 4, 'changed': {'x': 2}}, ['y'], 'then')
        self.assertEqual(value, {'revision': 5, 'changed': {'x': 2, 'y': 5}, 'updated_at': 'then'})


if __name__ == '__main__':
    unittest.main()
