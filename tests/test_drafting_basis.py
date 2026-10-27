"""A job's result lands only while its part is unchanged, on synthetic drafts (no store)."""

import copy
import json
import re
import unittest

import marketing_studio  # noqa: F401  Puts core/ on the path.
from studio_core.drafting import basis
from studio_core.drafting.parts import MARKDOWN, Codec

STALE = 'The draft changed while this was being written. Run it again.'
NUMBER = 'Check the facts: this changes a number.'


def draft(first='First text.', opening='An opening.'):
    return {
        'title': 'A title',
        'opening': opening,
        'sections': [
            {'id': 'aaaaaaaa', 'heading': 'First', 'brief': '', 'text': first},
            {'id': 'bbbbbbbb', 'heading': 'Second', 'brief': '', 'text': 'Second text.'},
        ],
        'revision': 1,
    }


def meta(value, part='aaaaaaaa', **extra):
    return {'part': part, 'basis': basis.fingerprint(MARKDOWN.text_of(value, part)), **extra}


class LandPartTests(unittest.TestCase):
    def test_a_result_lands_only_while_its_part_is_unchanged(self):
        value = draft()
        asked = meta(value)
        part, before, text, flag = basis.land_part(value, asked, '## First\n\nNew first.')
        self.assertEqual((part, before, text, flag), ('aaaaaaaa', 'First text.', 'New first.', ''))
        changed = draft('Typed meanwhile.')
        with self.assertRaisesRegex(ValueError, '^' + STALE + '$'):
            basis.land_part(changed, asked, 'New first.')
        removed = draft()
        removed['sections'] = removed['sections'][1:]
        with self.assertRaisesRegex(ValueError, '^' + STALE + '$'):
            basis.land_part(removed, asked, 'New first.')

    def test_an_opening_result_loses_a_leading_title_line(self):
        value = draft()
        found = basis.land_part(value, meta(value, 'opening'), '# A title\n\nA new opening.')
        self.assertEqual(found[2], 'A new opening.')

    def test_a_result_that_adds_a_section_is_refused(self):
        value = draft()
        with self.assertRaisesRegex(ValueError, re.escape(MARKDOWN.added_message('##'))):
            basis.land_part(value, meta(value), 'Text.\n\n## New\n\nMore.')

    def test_a_rewrite_that_changes_a_number_is_flagged_and_still_returned(self):
        value = draft('In 2024.')
        found = basis.land_part(value, meta(value), 'In 2025.')
        self.assertEqual(found[2:], ('In 2025.', NUMBER))
        value = draft('In 2024 we met.')
        asked = meta(value, selection='2024', start=3)
        found = basis.land_selection(value, asked, '2025')
        self.assertEqual(found[2:], ('In 2025 we met.', NUMBER))

    def test_a_deck_codec_says_deck(self):
        deck = Codec(fixed=(), single=(), thing='deck')
        value = draft()
        asked = meta(value)
        value['sections'][0]['text'] = 'Changed.'
        with self.assertRaisesRegex(ValueError, 'The deck changed while this was being written.'):
            basis.land_part(value, asked, 'New.', deck)

    def test_a_codec_s_landed_hook_shapes_the_text(self):
        codec = MARKDOWN.replace(landed=lambda value, before, text: text + ' [kept]')
        value = draft()
        self.assertEqual(basis.land_part(value, meta(value), 'New.', codec)[2], 'New. [kept]')


class LandSelectionTests(unittest.TestCase):
    def test_a_selection_lands_on_the_word_chosen(self):
        value = draft('one two one')
        asked = meta(value, selection='one', start=8)
        self.assertEqual(basis.land_selection(value, asked, 'ONE')[2], 'one two ONE')
        moved = draft('zero one two')
        self.assertEqual(basis.land_selection(moved, asked, 'ONE')[2], 'zero ONE two')
        twice = draft('one zero one two')
        with self.assertRaisesRegex(ValueError, '^' + re.escape(basis.MOVED) + '$'):
            basis.land_selection(twice, asked, 'ONE')

    def test_a_selection_keeps_its_own_spaces(self):
        value = draft('one two three')
        asked = meta(value, selection=' two ', start=3)
        self.assertEqual(basis.land_selection(value, asked, '2')[2], 'one 2 three')

    def test_a_title_selection_stays_on_one_line(self):
        value = draft()
        asked = meta(value, 'title', selection='title', start=2)
        self.assertEqual(basis.land_selection(value, asked, 'new\nheading')[2], 'A new heading')

    def test_a_selection_in_a_part_that_is_gone_is_stale(self):
        value = draft()
        asked = meta(value, selection='First', start=0)
        value['sections'] = []
        with self.assertRaisesRegex(ValueError, STALE):
            basis.land_selection(value, asked, 'Then')


class LandSectionsTests(unittest.TestCase):
    def asked(self, value):
        return {'part': 'sections', 'basis': basis.pass_basis(value)}

    def test_a_whole_draft_result_names_only_known_sections(self):
        value = draft()
        content = json.dumps([{'id': 'aaaaaaaa', 'text': 'New first.'},
                              {'id': 'bbbbbbbb', 'text': 'Second text.'},
                              {'id': 'opening', 'text': '# A title\n\nNew opening.'}])
        changes, added = basis.land_sections(value, self.asked(value),
                                             '```json\n' + content + '\n```')
        self.assertEqual(changes, {'aaaaaaaa': ('First text.', 'New first.', ''),
                                   'opening': ('An opening.', 'New opening.', '')})
        self.assertEqual(added, [])
        unknown = json.dumps([{'id': 'cccccccc', 'text': 'x'}])
        with self.assertRaisesRegex(ValueError, re.escape(basis.UNKNOWN)):
            basis.land_sections(value, self.asked(value), unknown)
        with self.assertRaisesRegex(ValueError, re.escape(basis.NOT_LISTED)):
            basis.land_sections(value, self.asked(value), '{"id": "x"}')

    def test_a_whole_draft_result_after_any_change_is_stale(self):
        value = draft()
        asked = self.asked(value)
        with self.assertRaisesRegex(ValueError, STALE):
            basis.land_sections(draft(opening='Typed.'), asked, '[]')

    def test_a_studio_may_divide_a_part(self):
        value = draft()
        value['sections'] = []
        content = json.dumps([{'id': 'opening', 'text': 'Lead.\n\n## A\n\nB.'}])
        added = [{'id': 'cccccccc', 'heading': 'A', 'brief': '', 'text': 'B.'}]
        changes, found = basis.land_sections(
            value, self.asked(value), content,
            divide=lambda part, text: ('Lead.', copy.deepcopy(added)),
        )
        self.assertEqual(changes['opening'][1], 'Lead.')
        self.assertEqual(found, added)


class SettleTests(unittest.TestCase):
    def test_a_ready_result_not_yet_landed_is_still_under_way(self):
        self.assertTrue(basis.busy({'status': 'ready'}))
        self.assertFalse(basis.busy({'status': 'ready', 'settled_at': 'x'}))
        self.assertTrue(basis.busy({'status': 'working'}))
        self.assertTrue(basis.unsettled({'status': 'ready'}))

    def test_settling_says_what_went_wrong_once(self):
        def full():
            raise OSError('full')

        job = basis.settle({'id': 'x'}, full, lambda: 'then')
        self.assertFalse(job['applied'])
        self.assertTrue(job['error'].startswith('This result could not be saved: full'))
        self.assertTrue(job['error'].endswith(' Nothing was changed; run it again.'))
        self.assertEqual(job['settled_at'], 'then')

    def test_a_refusal_is_said_as_it_is(self):
        def stale():
            raise ValueError(STALE)

        job = basis.settle({}, stale, lambda: 'then')
        self.assertEqual((job['applied'], job['error']), (False, STALE))
        landed = basis.settle({}, lambda: None, lambda: 'then')
        self.assertEqual((landed['applied'], landed['error']), (True, ''))

    def test_gaps_are_merged_once_each_and_capped(self):
        value = {'gaps': ['Old.']}
        basis.merge_gaps(value, {'gaps': ['Old.', ' New. ', '', 3] + ['g' + str(n) for n in range(60)]})
        self.assertEqual(value['gaps'][:0], [])
        self.assertEqual(len(value['gaps']), basis.GAPS)
        self.assertNotIn(' New. ', value['gaps'])


if __name__ == '__main__':
    unittest.main()
